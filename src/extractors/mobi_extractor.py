"""MOBI/AZW metadata extractor"""
from typing import Optional
from pathlib import Path
import struct
from .base import BaseExtractor, EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MOBIExtractor(BaseExtractor):
    """Metadata extractor for MOBI and AZW files"""

    def __init__(self):
        super().__init__()
        self.supported_formats = ['.mobi', '.azw', '.azw3']

    def can_handle(self, file_path: str) -> bool:
        """Check if file is a MOBI/AZW file"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def extract(self, file_path: str) -> EbookMetadata:
        """
        Extract metadata from MOBI/AZW file

        Args:
            file_path: Path to MOBI/AZW file

        Returns:
            Extracted metadata
        """
        logger.info(f"Extracting metadata from MOBI/AZW: {file_path}")

        metadata = EbookMetadata()

        # Get file info
        file_info = self._get_file_info(file_path)
        metadata.file_path = file_info['file_path']
        metadata.file_format = file_info['file_format']
        metadata.file_size = file_info['file_size']

        try:
            # Extract MOBI metadata using mobi library
            import mobi

            # Extract MOBI file
            tempdir, filepath = mobi.extract(file_path)

            # Parse the metadata from MOBI header
            with open(file_path, 'rb') as f:
                # Read MOBI header
                mobi_header = self._parse_mobi_header(f)

                if mobi_header:
                    # Extract EXTH records (Extended Header)
                    exth_records = mobi_header.get('exth_records', {})

                    # Map EXTH record types to metadata
                    # EXTH record type 100: Author
                    if 100 in exth_records:
                        authors = exth_records[100]
                        if isinstance(authors, list):
                            metadata.authors = authors
                        else:
                            metadata.authors = [authors]

                    # EXTH record type 503: Title
                    if 503 in exth_records:
                        metadata.title = exth_records[503]

                    # EXTH record type 101: Publisher
                    if 101 in exth_records:
                        metadata.publisher = exth_records[101]

                    # EXTH record type 106: Publishing date
                    if 106 in exth_records:
                        metadata.published_date = exth_records[106]

                    # EXTH record type 103: Description
                    if 103 in exth_records:
                        metadata.description = exth_records[103]

                    # EXTH record type 104: ISBN
                    if 104 in exth_records:
                        isbn = exth_records[104].replace('-', '')
                        if len(isbn) == 13:
                            metadata.isbn13 = isbn
                        elif len(isbn) == 10:
                            metadata.isbn = isbn

                    # EXTH record type 105: Subject/Category
                    if 105 in exth_records:
                        subjects = exth_records[105]
                        if isinstance(subjects, list):
                            metadata.subjects = subjects
                        else:
                            metadata.subjects = [subjects]

                    # EXTH record type 524: Language
                    if 524 in exth_records:
                        metadata.language = exth_records[524]

            # Fallback to filename if metadata is poor
            if not metadata.title or not metadata.authors:
                logger.warning(f"Limited metadata in MOBI/AZW, attempting filename extraction")
                filename_meta = self._extract_filename_metadata(file_path)
                if not metadata.title and filename_meta['title']:
                    metadata.title = filename_meta['title']
                if not metadata.authors and filename_meta['author']:
                    metadata.authors = [filename_meta['author']]

            metadata._calculate_completeness()
            logger.info(f"MOBI/AZW metadata extraction complete. Completeness: {metadata.metadata_completeness:.2%}")

        except ImportError:
            logger.warning("mobi library not available, using basic extraction")
            metadata = self._basic_extraction(file_path)
        except Exception as e:
            logger.error(f"Error extracting MOBI/AZW metadata: {str(e)}")
            # Fall back to filename extraction
            filename_meta = self._extract_filename_metadata(file_path)
            metadata.title = filename_meta['title']
            if filename_meta['author']:
                metadata.authors = [filename_meta['author']]

        return metadata

    def _parse_mobi_header(self, file_handle) -> Optional[dict]:
        """
        Parse MOBI header to extract metadata

        Args:
            file_handle: Open file handle

        Returns:
            Dictionary of metadata or None
        """
        try:
            # Read PalmDB header
            file_handle.seek(0)
            palm_header = file_handle.read(78)

            # Check for MOBI signature
            if palm_header[60:68] != b'BOOKMOBI':
                return None

            # Find MOBI header offset
            file_handle.seek(78)
            record_info = file_handle.read(8)
            offset = struct.unpack('>I', record_info[0:4])[0]

            # Read MOBI header
            file_handle.seek(offset)
            mobi_header = file_handle.read(256)

            # Check if EXTH header exists
            exth_flag = struct.unpack('>I', mobi_header[128:132])[0]

            result = {'exth_records': {}}

            if exth_flag & 0x40:  # EXTH exists
                # Find EXTH header
                exth_offset = offset + struct.unpack('>I', mobi_header[20:24])[0]
                file_handle.seek(exth_offset)

                exth_header = file_handle.read(12)
                if exth_header[0:4] == b'EXTH':
                    record_count = struct.unpack('>I', exth_header[8:12])[0]

                    # Read EXTH records
                    pos = exth_offset + 12
                    for _ in range(record_count):
                        file_handle.seek(pos)
                        record_header = file_handle.read(8)
                        record_type = struct.unpack('>I', record_header[0:4])[0]
                        record_length = struct.unpack('>I', record_header[4:8])[0]

                        if record_length > 8:
                            record_data = file_handle.read(record_length - 8)
                            try:
                                # Try to decode as UTF-8
                                result['exth_records'][record_type] = record_data.decode('utf-8', errors='ignore').strip()
                            except:
                                pass

                        pos += record_length

            return result

        except Exception as e:
            logger.debug(f"Error parsing MOBI header: {str(e)}")
            return None

    def _basic_extraction(self, file_path: str) -> EbookMetadata:
        """
        Basic metadata extraction when mobi library is not available

        Args:
            file_path: Path to MOBI file

        Returns:
            Basic metadata
        """
        metadata = EbookMetadata()

        file_info = self._get_file_info(file_path)
        metadata.file_path = file_info['file_path']
        metadata.file_format = file_info['file_format']
        metadata.file_size = file_info['file_size']

        # Extract from filename
        filename_meta = self._extract_filename_metadata(file_path)
        metadata.title = filename_meta['title']
        if filename_meta['author']:
            metadata.authors = [filename_meta['author']]

        return metadata
