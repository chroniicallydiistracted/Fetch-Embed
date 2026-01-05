"""Calibre ebook-meta based writer for maximum stability"""
import subprocess
import json
from pathlib import Path
from typing import Optional, List
from .base import BaseWriter
from ..extractors.base import EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CalibreWriter(BaseWriter):
    """
    Metadata writer using Calibre's ebook-meta command-line tool

    This provides maximum stability and format support by leveraging
    Calibre's battle-tested metadata handling.
    """

    def __init__(self, backup: bool = True, backup_dir: str = ".backups"):
        super().__init__(backup, backup_dir)
        # Calibre supports a wide range of formats
        self.supported_formats = [
            '.epub', '.mobi', '.azw', '.azw3', '.azw4',
            '.pdf', '.lit', '.lrf', '.fb2', '.pdb',
            '.cbz', '.cbr', '.cbc', '.chm', '.htmlz',
            '.odt', '.rtf', '.txt', '.kepub'
        ]
        self._check_calibre_installed()

    def _check_calibre_installed(self) -> bool:
        """
        Check if Calibre (ebook-meta) is installed and available

        Returns:
            True if available, False otherwise
        """
        try:
            result = subprocess.run(
                ['ebook-meta', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"Calibre ebook-meta available: {version}")
                return True
            else:
                logger.warning("ebook-meta command found but returned error")
                return False
        except FileNotFoundError:
            logger.error("Calibre ebook-meta not found. Please install Calibre.")
            return False
        except Exception as e:
            logger.error(f"Error checking for ebook-meta: {str(e)}")
            return False

    def can_handle(self, file_path: str) -> bool:
        """Check if file format is supported by Calibre"""
        return Path(file_path).suffix.lower() in self.supported_formats

    def write(self, file_path: str, metadata: EbookMetadata) -> bool:
        """
        Write metadata to ebook file using ebook-meta

        Args:
            file_path: Path to ebook file
            metadata: Metadata to write

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_file(file_path):
            return False

        logger.info(f"Writing metadata using Calibre ebook-meta: {file_path}")

        # Create backup
        backup_path = self.backup_file(file_path)

        try:
            # Build ebook-meta command
            cmd = self._build_command(file_path, metadata)

            # Execute ebook-meta
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Successfully wrote metadata to: {file_path}")
                logger.debug(f"ebook-meta output: {result.stdout}")
                return True
            else:
                logger.error(f"ebook-meta failed with code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")

                # Restore from backup
                if backup_path:
                    logger.info("Attempting to restore from backup...")
                    self.restore_from_backup(file_path, backup_path)

                return False

        except subprocess.TimeoutExpired:
            logger.error("ebook-meta command timed out")
            if backup_path:
                self.restore_from_backup(file_path, backup_path)
            return False
        except Exception as e:
            logger.error(f"Error executing ebook-meta: {str(e)}")
            if backup_path:
                self.restore_from_backup(file_path, backup_path)
            return False

    def _build_command(self, file_path: str, metadata: EbookMetadata) -> List[str]:
        """
        Build ebook-meta command with metadata parameters

        Args:
            file_path: Path to ebook file
            metadata: Metadata to apply

        Returns:
            Command as list of strings
        """
        cmd = ['ebook-meta', file_path]

        # Title
        if metadata.title:
            cmd.extend(['--title', metadata.title])

        # Authors
        if metadata.authors:
            authors_str = ' & '.join(metadata.authors)
            cmd.extend(['--authors', authors_str])

        # ISBN
        if metadata.isbn13:
            cmd.extend(['--isbn', metadata.isbn13])
        elif metadata.isbn:
            cmd.extend(['--isbn', metadata.isbn])

        # Publisher
        if metadata.publisher:
            cmd.extend(['--publisher', metadata.publisher])

        # Published date
        if metadata.published_date:
            cmd.extend(['--date', metadata.published_date])

        # Language
        if metadata.language:
            cmd.extend(['--language', metadata.language])

        # Description/comments
        if metadata.description:
            cmd.extend(['--comments', metadata.description])

        # Tags (subjects)
        if metadata.subjects:
            tags_str = ','.join(metadata.subjects)
            cmd.extend(['--tags', tags_str])

        # Series
        if metadata.series:
            cmd.extend(['--series', metadata.series])

        # Series index
        if metadata.series_index:
            cmd.extend(['--index', str(metadata.series_index)])

        # Rating
        if metadata.rating:
            # Rating should be 0-10 in Calibre
            rating_value = int(metadata.rating * 2)  # Convert 0-5 to 0-10
            cmd.extend(['--rating', str(rating_value)])

        logger.debug(f"ebook-meta command: {' '.join(cmd)}")

        return cmd

    def read_metadata(self, file_path: str) -> Optional[dict]:
        """
        Read metadata from ebook file using ebook-meta

        Args:
            file_path: Path to ebook file

        Returns:
            Metadata dictionary or None if failed
        """
        try:
            result = subprocess.run(
                ['ebook-meta', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Parse ebook-meta output
                metadata = self._parse_ebook_meta_output(result.stdout)
                return metadata
            else:
                logger.error(f"Failed to read metadata: {result.stderr}")
                return None

        except Exception as e:
            logger.error(f"Error reading metadata: {str(e)}")
            return None

    def _parse_ebook_meta_output(self, output: str) -> dict:
        """
        Parse ebook-meta text output into dictionary

        Args:
            output: Text output from ebook-meta

        Returns:
            Metadata dictionary
        """
        metadata = {}
        current_key = None
        current_value = []

        for line in output.split('\n'):
            if ':' in line and not line.startswith(' '):
                # Save previous key-value
                if current_key:
                    metadata[current_key] = '\n'.join(current_value).strip()

                # Start new key-value
                parts = line.split(':', 1)
                current_key = parts[0].strip()
                current_value = [parts[1].strip()] if len(parts) > 1 else []
            elif current_key and line.strip():
                # Continuation of previous value
                current_value.append(line.strip())

        # Save last key-value
        if current_key:
            metadata[current_key] = '\n'.join(current_value).strip()

        return metadata

    def write_opf(self, file_path: str, opf_path: str) -> bool:
        """
        Apply OPF metadata file directly to ebook

        Args:
            file_path: Path to ebook file
            opf_path: Path to OPF metadata file

        Returns:
            True if successful, False otherwise
        """
        if not self.validate_file(file_path):
            return False

        if not Path(opf_path).exists():
            logger.error(f"OPF file not found: {opf_path}")
            return False

        logger.info(f"Applying OPF metadata to: {file_path}")

        # Create backup
        backup_path = self.backup_file(file_path)

        try:
            # Use ebook-meta with --from-opf option
            cmd = ['ebook-meta', file_path, '--from-opf', opf_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Successfully applied OPF metadata to: {file_path}")
                return True
            else:
                logger.error(f"Failed to apply OPF: {result.stderr}")
                if backup_path:
                    self.restore_from_backup(file_path, backup_path)
                return False

        except Exception as e:
            logger.error(f"Error applying OPF: {str(e)}")
            if backup_path:
                self.restore_from_backup(file_path, backup_path)
            return False

    def export_opf(self, file_path: str, output_path: str) -> bool:
        """
        Export current metadata to OPF file

        Args:
            file_path: Path to ebook file
            output_path: Path to save OPF file

        Returns:
            True if successful, False otherwise
        """
        try:
            cmd = ['ebook-meta', file_path, '--to-opf', output_path]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info(f"Exported OPF metadata to: {output_path}")
                return True
            else:
                logger.error(f"Failed to export OPF: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error exporting OPF: {str(e)}")
            return False
