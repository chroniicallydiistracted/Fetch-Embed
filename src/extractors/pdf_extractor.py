"""PDF metadata extractor"""
from typing import Optional
from pathlib import Path
import pypdf
from .base import BaseExtractor, EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class PDFExtractor(BaseExtractor):
    """Metadata extractor for PDF files"""

    def __init__(self):
        super().__init__()
        self.supported_formats = ['.pdf']

    def can_handle(self, file_path: str) -> bool:
        """Check if file is a PDF"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def extract(self, file_path: str) -> EbookMetadata:
        """
        Extract metadata from PDF file

        Args:
            file_path: Path to PDF file

        Returns:
            Extracted metadata
        """
        logger.info(f"Extracting metadata from PDF: {file_path}")

        metadata = EbookMetadata()

        # Get file info
        file_info = self._get_file_info(file_path)
        metadata.file_path = file_info['file_path']
        metadata.file_format = file_info['file_format']
        metadata.file_size = file_info['file_size']

        try:
            # Read PDF file
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)

                # Get metadata
                pdf_metadata = pdf_reader.metadata

                if pdf_metadata:
                    # Extract title
                    if pdf_metadata.title:
                        metadata.title = pdf_metadata.title

                    # Extract author
                    if pdf_metadata.author:
                        # Some PDFs have multiple authors separated by various delimiters
                        authors = self._parse_authors(pdf_metadata.author)
                        metadata.authors = authors

                    # Extract other metadata
                    if pdf_metadata.subject:
                        metadata.description = pdf_metadata.subject

                    if pdf_metadata.creator:
                        metadata.custom_fields['creator'] = pdf_metadata.creator

                    if pdf_metadata.producer:
                        metadata.custom_fields['producer'] = pdf_metadata.producer

                    # Some PDFs include keywords
                    if hasattr(pdf_metadata, 'keywords') and pdf_metadata.keywords:
                        keywords = [k.strip() for k in pdf_metadata.keywords.split(',')]
                        metadata.tags = keywords
                        metadata.subjects = keywords

                # Get page count
                metadata.pages = len(pdf_reader.pages)

                # Try to extract ISBN from text if not in metadata
                if not metadata.isbn and not metadata.isbn13:
                    isbn = self._extract_isbn_from_text(pdf_reader)
                    if isbn:
                        if len(isbn) == 13:
                            metadata.isbn13 = isbn
                        elif len(isbn) == 10:
                            metadata.isbn = isbn

            # If no metadata found, try filename
            if not metadata.title or not metadata.authors:
                logger.warning(f"Limited metadata in PDF, attempting filename extraction")
                filename_meta = self._extract_filename_metadata(file_path)
                if not metadata.title and filename_meta['title']:
                    metadata.title = filename_meta['title']
                if not metadata.authors and filename_meta['author']:
                    metadata.authors = [filename_meta['author']]

            metadata._calculate_completeness()
            logger.info(f"PDF metadata extraction complete. Completeness: {metadata.metadata_completeness:.2%}")

        except Exception as e:
            logger.error(f"Error extracting PDF metadata: {str(e)}")
            # Fall back to filename extraction
            filename_meta = self._extract_filename_metadata(file_path)
            metadata.title = filename_meta['title']
            if filename_meta['author']:
                metadata.authors = [filename_meta['author']]

        return metadata

    def _parse_authors(self, author_string: str) -> list:
        """
        Parse author string into list of authors

        Args:
            author_string: Author string from PDF metadata

        Returns:
            List of author names
        """
        # Try different separators
        separators = [';', ',', ' and ', ' & ']

        for sep in separators:
            if sep in author_string:
                return [a.strip() for a in author_string.split(sep) if a.strip()]

        # No separator found, return as single author
        return [author_string.strip()]

    def _extract_isbn_from_text(self, pdf_reader: pypdf.PdfReader) -> Optional[str]:
        """
        Try to extract ISBN from the first few pages of the PDF

        Args:
            pdf_reader: PDF reader object

        Returns:
            ISBN if found, None otherwise
        """
        import re

        # Only check first 3 pages
        max_pages = min(3, len(pdf_reader.pages))

        isbn_pattern = r'ISBN[-\s]?(?:13)?:?\s?([\d-]{10,17})'

        for i in range(max_pages):
            try:
                text = pdf_reader.pages[i].extract_text()
                matches = re.findall(isbn_pattern, text, re.IGNORECASE)

                for match in matches:
                    # Clean ISBN
                    isbn = match.replace('-', '').replace(' ', '')
                    # Validate length
                    if len(isbn) in [10, 13] and isbn.isdigit():
                        return isbn
            except Exception as e:
                logger.debug(f"Error extracting text from page {i}: {str(e)}")
                continue

        return None
