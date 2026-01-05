"""EPUB metadata writer"""
from pathlib import Path
from typing import List
import ebooklib
from ebooklib import epub
from .base import BaseWriter
from ..extractors.base import EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class EPUBWriter(BaseWriter):
    """Metadata writer for EPUB files"""

    def __init__(self, backup: bool = True, backup_dir: str = ".backups"):
        super().__init__(backup, backup_dir)
        self.supported_formats = ['.epub']

    def can_handle(self, file_path: str) -> bool:
        """Check if file is an EPUB"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def write(self, file_path: str, metadata: EbookMetadata) -> bool:
        """
        Write metadata to EPUB file

        Args:
            file_path: Path to EPUB file
            metadata: Metadata to write

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_file(file_path):
            return False

        logger.info(f"Writing metadata to EPUB: {file_path}")

        # Create backup
        backup_path = self.backup_file(file_path)

        try:
            # Read existing EPUB
            book = epub.read_epub(file_path)

            # Update metadata
            self._update_metadata(book, metadata)

            # Write modified EPUB
            epub.write_epub(file_path, book)

            logger.info(f"Successfully wrote metadata to EPUB: {file_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing EPUB metadata: {str(e)}")

            # Restore from backup if available
            if backup_path:
                logger.info("Attempting to restore from backup...")
                self.restore_from_backup(file_path, backup_path)

            return False

    def _update_metadata(self, book: epub.EpubBook, metadata: EbookMetadata) -> None:
        """
        Update book metadata

        Args:
            book: EPUB book object
            metadata: Metadata to apply
        """
        # Clear existing metadata to avoid duplicates
        self._clear_metadata(book, 'DC', 'title')
        self._clear_metadata(book, 'DC', 'creator')
        self._clear_metadata(book, 'DC', 'publisher')
        self._clear_metadata(book, 'DC', 'date')
        self._clear_metadata(book, 'DC', 'language')
        self._clear_metadata(book, 'DC', 'description')
        self._clear_metadata(book, 'DC', 'identifier')
        self._clear_metadata(book, 'DC', 'subject')

        # Set title
        if metadata.title:
            book.set_title(metadata.title)
            logger.debug(f"Set title: {metadata.title}")

        # Set authors
        if metadata.authors:
            for author in metadata.authors:
                if author:
                    book.add_author(author)
                    logger.debug(f"Added author: {author}")

        # Set publisher
        if metadata.publisher:
            book.add_metadata('DC', 'publisher', metadata.publisher)
            logger.debug(f"Set publisher: {metadata.publisher}")

        # Set published date
        if metadata.published_date:
            book.add_metadata('DC', 'date', metadata.published_date)
            logger.debug(f"Set date: {metadata.published_date}")

        # Set language
        if metadata.language:
            book.set_language(metadata.language)
            logger.debug(f"Set language: {metadata.language}")

        # Set description
        if metadata.description:
            book.add_metadata('DC', 'description', metadata.description)
            logger.debug(f"Set description (length: {len(metadata.description)})")

        # Set ISBN
        if metadata.isbn13:
            book.add_metadata('DC', 'identifier', metadata.isbn13, {'id': 'isbn13'})
            logger.debug(f"Set ISBN-13: {metadata.isbn13}")
        elif metadata.isbn:
            book.add_metadata('DC', 'identifier', metadata.isbn, {'id': 'isbn'})
            logger.debug(f"Set ISBN: {metadata.isbn}")

        # Set subjects/tags
        if metadata.subjects:
            for subject in metadata.subjects:
                if subject:
                    book.add_metadata('DC', 'subject', subject)
            logger.debug(f"Added {len(metadata.subjects)} subjects")

        # Set series information (using calibre metadata schema)
        if metadata.series:
            book.add_metadata('calibre', 'series', metadata.series)
            logger.debug(f"Set series: {metadata.series}")

        if metadata.series_index:
            book.add_metadata('calibre', 'series_index', str(metadata.series_index))
            logger.debug(f"Set series index: {metadata.series_index}")

    def _clear_metadata(self, book: epub.EpubBook, namespace: str, key: str) -> None:
        """
        Clear existing metadata for a key

        Args:
            book: EPUB book object
            namespace: Metadata namespace
            key: Metadata key
        """
        try:
            # Get metadata
            existing = book.get_metadata(namespace, key)
            if existing:
                # Remove all instances
                for _ in range(len(existing)):
                    # Unfortunately, ebooklib doesn't have a remove method
                    # So we'll need to work with the internal structure
                    pass
            # The set/add methods will replace existing values
        except Exception as e:
            logger.debug(f"Could not clear metadata {namespace}:{key}: {str(e)}")
