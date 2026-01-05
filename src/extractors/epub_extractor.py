"""EPUB metadata extractor"""
from typing import Optional, List
from pathlib import Path
import ebooklib
from ebooklib import epub
from .base import BaseExtractor, EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EPUBExtractor(BaseExtractor):
    """Metadata extractor for EPUB files"""

    def __init__(self):
        super().__init__()
        self.supported_formats = ['.epub']

    def can_handle(self, file_path: str) -> bool:
        """Check if file is an EPUB"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def extract(self, file_path: str) -> EbookMetadata:
        """
        Extract metadata from EPUB file

        Args:
            file_path: Path to EPUB file

        Returns:
            Extracted metadata
        """
        logger.info(f"Extracting metadata from EPUB: {file_path}")

        metadata = EbookMetadata()

        # Get file info
        file_info = self._get_file_info(file_path)
        metadata.file_path = file_info['file_path']
        metadata.file_format = file_info['file_format']
        metadata.file_size = file_info['file_size']

        try:
            # Read EPUB file
            book = epub.read_epub(file_path)

            # Extract Dublin Core metadata
            metadata.title = self._get_metadata(book, 'DC', 'title')
            metadata.publisher = self._get_metadata(book, 'DC', 'publisher')
            metadata.language = self._get_metadata(book, 'DC', 'language')
            metadata.description = self._get_metadata(book, 'DC', 'description')
            metadata.published_date = self._get_metadata(book, 'DC', 'date')

            # Extract authors
            authors = self._get_metadata_list(book, 'DC', 'creator')
            if authors:
                metadata.authors = authors

            # Extract ISBN
            identifiers = self._get_metadata_list(book, 'DC', 'identifier')
            for identifier in identifiers:
                if identifier:
                    clean_id = identifier.replace('-', '').replace(' ', '').upper()
                    if 'ISBN' in clean_id or len(clean_id) in [10, 13]:
                        # Extract just the ISBN number
                        isbn = ''.join(c for c in clean_id if c.isdigit())
                        if len(isbn) == 13:
                            metadata.isbn13 = isbn
                        elif len(isbn) == 10:
                            metadata.isbn = isbn

            # Extract subjects/tags
            subjects = self._get_metadata_list(book, 'DC', 'subject')
            if subjects:
                metadata.subjects = subjects
                metadata.tags = subjects

            # Try to extract series information from metadata
            # Some EPUB files use calibre metadata
            series = self._get_metadata(book, 'calibre', 'series')
            if series:
                metadata.series = series

            series_index = self._get_metadata(book, 'calibre', 'series_index')
            if series_index:
                try:
                    metadata.series_index = int(float(series_index))
                except (ValueError, TypeError):
                    pass

            # If no metadata found, try filename
            if not metadata.title or not metadata.authors:
                logger.warning(f"Limited metadata in EPUB, attempting filename extraction")
                filename_meta = self._extract_filename_metadata(file_path)
                if not metadata.title and filename_meta['title']:
                    metadata.title = filename_meta['title']
                if not metadata.authors and filename_meta['author']:
                    metadata.authors = [filename_meta['author']]

            metadata._calculate_completeness()
            logger.info(f"EPUB metadata extraction complete. Completeness: {metadata.metadata_completeness:.2%}")

        except Exception as e:
            logger.error(f"Error extracting EPUB metadata: {str(e)}")
            # Fall back to filename extraction
            filename_meta = self._extract_filename_metadata(file_path)
            metadata.title = filename_meta['title']
            if filename_meta['author']:
                metadata.authors = [filename_meta['author']]

        return metadata

    def _get_metadata(self, book: epub.EpubBook, namespace: str, key: str) -> Optional[str]:
        """
        Get single metadata value from EPUB

        Args:
            book: EPUB book object
            namespace: Metadata namespace (e.g., 'DC')
            key: Metadata key

        Returns:
            Metadata value or None
        """
        try:
            values = book.get_metadata(namespace, key)
            if values and len(values) > 0:
                # values is a list of tuples: [(value, attributes), ...]
                return values[0][0] if values[0][0] else None
        except Exception as e:
            logger.debug(f"Error getting metadata {namespace}:{key}: {str(e)}")
        return None

    def _get_metadata_list(self, book: epub.EpubBook, namespace: str, key: str) -> List[str]:
        """
        Get multiple metadata values from EPUB

        Args:
            book: EPUB book object
            namespace: Metadata namespace
            key: Metadata key

        Returns:
            List of metadata values
        """
        try:
            values = book.get_metadata(namespace, key)
            if values:
                return [v[0] for v in values if v[0]]
        except Exception as e:
            logger.debug(f"Error getting metadata list {namespace}:{key}: {str(e)}")
        return []
