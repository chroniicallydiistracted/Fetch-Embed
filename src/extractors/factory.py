"""Factory for creating appropriate metadata extractors"""
from typing import Optional, List
from pathlib import Path
from .base import BaseExtractor, EbookMetadata
from .epub_extractor import EPUBExtractor
from .pdf_extractor import PDFExtractor
from .mobi_extractor import MOBIExtractor
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ExtractorFactory:
    """Factory for creating metadata extractors"""

    def __init__(self):
        """Initialize factory with all available extractors"""
        self.extractors: List[BaseExtractor] = [
            EPUBExtractor(),
            PDFExtractor(),
            MOBIExtractor(),
        ]

    def get_extractor(self, file_path: str) -> Optional[BaseExtractor]:
        """
        Get appropriate extractor for the given file

        Args:
            file_path: Path to ebook file

        Returns:
            Extractor instance or None if no extractor found
        """
        for extractor in self.extractors:
            if extractor.can_handle(file_path):
                return extractor

        logger.warning(f"No extractor found for file: {file_path}")
        return None

    def extract_metadata(self, file_path: str) -> Optional[EbookMetadata]:
        """
        Extract metadata from file using appropriate extractor

        Args:
            file_path: Path to ebook file

        Returns:
            Extracted metadata or None if extraction failed
        """
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return None

        extractor = self.get_extractor(file_path)
        if not extractor:
            return None

        try:
            metadata = extractor.extract(file_path)
            return metadata
        except Exception as e:
            logger.error(f"Error extracting metadata from {file_path}: {str(e)}")
            return None

    def get_supported_formats(self) -> List[str]:
        """
        Get list of all supported file formats

        Returns:
            List of supported file extensions
        """
        formats = []
        for extractor in self.extractors:
            formats.extend(extractor.supported_formats)
        return sorted(set(formats))
