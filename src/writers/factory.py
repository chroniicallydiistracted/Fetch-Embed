"""Factory for creating appropriate metadata writers"""
from typing import Optional, List
from pathlib import Path
from .base import BaseWriter
from .calibre_writer import CalibreWriter
from .epub_writer import EPUBWriter
from ..extractors.base import EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WriterFactory:
    """Factory for creating metadata writers"""

    def __init__(self, backup: bool = True, backup_dir: str = ".backups",
                 prefer_calibre: bool = True):
        """
        Initialize factory

        Args:
            backup: Whether to backup files before modification
            backup_dir: Directory for backups
            prefer_calibre: Whether to prefer Calibre writer when available
        """
        self.backup = backup
        self.backup_dir = backup_dir
        self.prefer_calibre = prefer_calibre
        self.writers: List[BaseWriter] = []
        self._initialize_writers()

    def _initialize_writers(self):
        """Initialize all available writers"""

        # Try to initialize Calibre writer first (most stable and comprehensive)
        if self.prefer_calibre:
            try:
                calibre_writer = CalibreWriter(
                    backup=self.backup,
                    backup_dir=self.backup_dir
                )
                # Check if Calibre is actually available
                if calibre_writer._check_calibre_installed():
                    self.writers.append(calibre_writer)
                    logger.info("Calibre writer initialized (preferred)")
                else:
                    logger.warning("Calibre not available, will use fallback writers")
            except Exception as e:
                logger.error(f"Failed to initialize Calibre writer: {str(e)}")

        # Fallback to format-specific writers if Calibre not available
        if not self.writers:
            logger.info("Using format-specific writers")
            self.writers.append(
                EPUBWriter(backup=self.backup, backup_dir=self.backup_dir)
            )
            # Add other format-specific writers here if needed

        logger.info(f"Initialized {len(self.writers)} writer(s)")

    def get_writer(self, file_path: str) -> Optional[BaseWriter]:
        """
        Get appropriate writer for the given file

        Args:
            file_path: Path to ebook file

        Returns:
            Writer instance or None if no writer found
        """
        for writer in self.writers:
            if writer.can_handle(file_path):
                logger.debug(f"Selected writer: {writer.__class__.__name__}")
                return writer

        logger.warning(f"No writer found for file: {file_path}")
        return None

    def write_metadata(self, file_path: str, metadata: EbookMetadata) -> bool:
        """
        Write metadata to file using appropriate writer

        Args:
            file_path: Path to ebook file
            metadata: Metadata to write

        Returns:
            True if successful, False otherwise
        """
        if not Path(file_path).exists():
            logger.error(f"File not found: {file_path}")
            return False

        writer = self.get_writer(file_path)
        if not writer:
            return False

        try:
            success = writer.write(file_path, metadata)
            return success
        except Exception as e:
            logger.error(f"Error writing metadata to {file_path}: {str(e)}")
            return False

    def get_supported_formats(self) -> List[str]:
        """
        Get list of all supported file formats

        Returns:
            List of supported file extensions
        """
        formats = []
        for writer in self.writers:
            formats.extend(writer.supported_formats)
        return sorted(set(formats))

    def is_calibre_available(self) -> bool:
        """
        Check if Calibre writer is available

        Returns:
            True if Calibre writer is initialized
        """
        return any(isinstance(w, CalibreWriter) for w in self.writers)
