"""Main metadata fetching and embedding service"""
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import asdict

from .extractors.factory import ExtractorFactory
from .extractors.base import EbookMetadata
from .api_clients.factory import APIClientFactory
from .api_clients.base import APIResult
from .matchers.confidence_scorer import ConfidenceScorer, ScoredMetadata
from .writers.factory import WriterFactory
from .utils.config import get_config, Config
from .utils.logger import setup_logger, get_logger

logger = get_logger(__name__)


class MetadataService:
    """
    Main service for fetching and embedding ebook metadata

    This service orchestrates the entire process:
    1. Extract existing metadata from ebook file
    2. Query multiple API providers for metadata
    3. Use fuzzy matching and confidence scoring to find best matches
    4. Aggregate and select highest confidence metadata for each field
    5. Write updated metadata back to the ebook file
    """

    def __init__(self, config_path: Optional[str] = None, log_level: str = "INFO"):
        """
        Initialize metadata service

        Args:
            config_path: Path to configuration file (optional)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        # Load configuration
        self.config = get_config(config_path)

        # Setup logging
        log_config = self.config.logging_config
        setup_logger(
            level=log_level or log_config.get('level', 'INFO'),
            log_file=log_config.get('file'),
            console=log_config.get('console', True)
        )

        logger.info("Initializing Fetch-Embed Metadata Service")

        # Initialize components
        self.extractor_factory = ExtractorFactory()
        self.api_factory = APIClientFactory(config_path)
        self.confidence_scorer = ConfidenceScorer(config_path)
        self.writer_factory = WriterFactory(
            backup=self.config.get('processing.backup_original', True),
            backup_dir=self.config.get('processing.backup_dir', '.backups'),
            prefer_calibre=True
        )

        logger.info(f"Service initialized with {len(self.api_factory.clients)} API clients")
        logger.info(f"Supported formats: {', '.join(self.extractor_factory.get_supported_formats())}")

    def process_file(self, file_path: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Process a single ebook file: extract, fetch, match, and embed metadata

        Args:
            file_path: Path to ebook file
            dry_run: If True, don't write metadata (only fetch and report)

        Returns:
            Dictionary with processing results and statistics
        """
        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Processing file: {file_path}")

        result = {
            'file_path': file_path,
            'success': False,
            'original_metadata': None,
            'api_results': {},
            'scored_metadata': None,
            'final_metadata': None,
            'metadata_written': False,
            'error': None
        }

        try:
            # Step 1: Extract existing metadata
            logger.info("Step 1/4: Extracting existing metadata...")
            original_metadata = self.extractor_factory.extract_metadata(file_path)

            if not original_metadata:
                raise Exception("Failed to extract metadata from file")

            result['original_metadata'] = original_metadata.to_dict()
            logger.info(f"Extracted metadata - Title: {original_metadata.title}, "
                       f"Authors: {', '.join(original_metadata.authors) if original_metadata.authors else 'None'}")
            logger.info(f"Metadata completeness: {original_metadata.metadata_completeness:.2%}")

            # Step 2: Query API providers
            logger.info("Step 2/4: Querying API providers...")
            api_results = self._fetch_from_apis(original_metadata)

            total_results = sum(len(results) for results in api_results.values())
            logger.info(f"Received {total_results} results from {len(api_results)} API providers")

            result['api_results'] = {
                source: [r.to_dict() for r in results]
                for source, results in api_results.items()
            }

            # Step 3: Score and aggregate results
            logger.info("Step 3/4: Scoring and aggregating metadata...")
            all_results = []
            for source, results in api_results.items():
                all_results.extend(results)

            if not all_results:
                logger.warning("No API results received, keeping original metadata")
                result['final_metadata'] = original_metadata.to_dict()
                result['success'] = True
                return result

            scored_metadata = self.confidence_scorer.score_results(
                original_metadata, all_results
            )

            result['scored_metadata'] = {
                'title': {'value': scored_metadata.title, 'score': scored_metadata.title_score},
                'authors': {'value': scored_metadata.authors, 'score': scored_metadata.authors_score},
                'isbn': {'value': scored_metadata.isbn, 'score': scored_metadata.isbn_score},
                'publisher': {'value': scored_metadata.publisher, 'score': scored_metadata.publisher_score},
                'overall_confidence': scored_metadata.overall_confidence,
                'sources': scored_metadata.sources
            }

            logger.info(f"Overall confidence: {scored_metadata.overall_confidence:.2%}")
            logger.info(f"Sources: {', '.join(scored_metadata.sources.keys())}")

            # Convert to EbookMetadata
            final_metadata = scored_metadata.to_ebook_metadata(original_metadata)
            result['final_metadata'] = final_metadata.to_dict()

            # Step 4: Write metadata (if not dry run)
            if not dry_run:
                logger.info("Step 4/4: Writing metadata to file...")
                write_success = self.writer_factory.write_metadata(file_path, final_metadata)

                if write_success:
                    logger.info(f"Successfully updated metadata for: {file_path}")
                    result['metadata_written'] = True
                    result['success'] = True
                else:
                    logger.error(f"Failed to write metadata to: {file_path}")
                    result['error'] = "Failed to write metadata"
            else:
                logger.info("Step 4/4: Skipping write (dry run mode)")
                result['success'] = True

            return result

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}", exc_info=True)
            result['error'] = str(e)
            return result

    def process_directory(self, directory_path: str, recursive: bool = True,
                         dry_run: bool = False) -> List[Dict[str, Any]]:
        """
        Process all ebook files in a directory

        Args:
            directory_path: Path to directory
            recursive: Whether to process subdirectories
            dry_run: If True, don't write metadata

        Returns:
            List of processing results for each file
        """
        logger.info(f"Processing directory: {directory_path} (recursive={recursive})")

        directory = Path(directory_path)
        if not directory.exists() or not directory.is_dir():
            logger.error(f"Directory not found: {directory_path}")
            return []

        # Get supported formats
        supported_formats = self.config.get(
            'processing.supported_formats',
            ['.epub', '.mobi', '.azw3', '.pdf']
        )

        # Find all ebook files
        ebook_files = []
        if recursive:
            for ext in supported_formats:
                ebook_files.extend(directory.rglob(f"*{ext}"))
        else:
            for ext in supported_formats:
                ebook_files.extend(directory.glob(f"*{ext}"))

        logger.info(f"Found {len(ebook_files)} ebook files to process")

        # Process each file
        results = []
        for i, file_path in enumerate(ebook_files, 1):
            logger.info(f"Processing file {i}/{len(ebook_files)}: {file_path.name}")
            result = self.process_file(str(file_path), dry_run=dry_run)
            results.append(result)

        # Summary
        successful = sum(1 for r in results if r['success'])
        written = sum(1 for r in results if r.get('metadata_written', False))

        logger.info(f"Directory processing complete: {successful}/{len(results)} successful, "
                   f"{written} files updated")

        return results

    def _fetch_from_apis(self, metadata: EbookMetadata) -> Dict[str, List[APIResult]]:
        """
        Fetch metadata from all API providers

        Args:
            metadata: Original metadata to use for searching

        Returns:
            Dictionary mapping source name to list of results
        """
        # Determine search parameters
        title = metadata.title
        author = metadata.authors[0] if metadata.authors else None
        isbn = metadata.isbn13 or metadata.isbn

        # If no metadata or poor quality, try filename
        use_filename = self.config.get('processing.use_filename_fallback', True)

        if use_filename and (not title or metadata.metadata_completeness < 0.3):
            logger.info("Using filename for API search (metadata incomplete)")
            # Extract from filename was already done in extractor
            # The title should already contain filename-based data

        # Query all APIs
        try:
            results = self.api_factory.search_all(
                title=title,
                author=author,
                isbn=isbn
            )
            return results
        except Exception as e:
            logger.error(f"Error fetching from APIs: {str(e)}")
            return {}

    def get_statistics(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate statistics from processing result

        Args:
            result: Processing result dictionary

        Returns:
            Statistics dictionary
        """
        stats = {
            'file': Path(result['file_path']).name,
            'success': result['success'],
            'api_sources': len(result.get('api_results', {})),
            'total_api_results': sum(
                len(results) for results in result.get('api_results', {}).values()
            ),
            'metadata_written': result.get('metadata_written', False)
        }

        if result.get('scored_metadata'):
            stats['overall_confidence'] = result['scored_metadata']['overall_confidence']
            stats['sources_used'] = list(result['scored_metadata']['sources'].keys())

        if result.get('error'):
            stats['error'] = result['error']

        return stats

    def close(self):
        """Close all resources"""
        logger.info("Closing Metadata Service")
        self.api_factory.close_all()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
