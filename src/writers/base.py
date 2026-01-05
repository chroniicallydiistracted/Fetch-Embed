"""Base metadata writer"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
import shutil
from datetime import datetime
from ..extractors.base import EbookMetadata
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BaseWriter(ABC):
    """Base class for metadata writers"""

    def __init__(self, backup: bool = True, backup_dir: str = ".backups"):
        """
        Initialize writer

        Args:
            backup: Whether to backup original file
            backup_dir: Directory for backups
        """
        self.backup = backup
        self.backup_dir = backup_dir
        self.supported_formats = []

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        Check if writer can handle the given file

        Args:
            file_path: Path to ebook file

        Returns:
            True if writer can handle the file
        """
        pass

    @abstractmethod
    def write(self, file_path: str, metadata: EbookMetadata) -> bool:
        """
        Write metadata to ebook file

        Args:
            file_path: Path to ebook file
            metadata: Metadata to write

        Returns:
            True if successful, False otherwise
        """
        pass

    def backup_file(self, file_path: str) -> Optional[str]:
        """
        Create backup of file before modification

        Args:
            file_path: Path to file to backup

        Returns:
            Path to backup file or None if backup failed
        """
        if not self.backup:
            return None

        try:
            path = Path(file_path)
            if not path.exists():
                logger.error(f"File not found for backup: {file_path}")
                return None

            # Create backup directory
            backup_path = path.parent / self.backup_dir
            backup_path.mkdir(exist_ok=True)

            # Create backup filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_path / f"{path.stem}_{timestamp}{path.suffix}"

            # Copy file
            shutil.copy2(file_path, backup_file)
            logger.info(f"Created backup: {backup_file}")

            return str(backup_file)

        except Exception as e:
            logger.error(f"Failed to create backup: {str(e)}")
            return None

    def restore_from_backup(self, file_path: str, backup_path: str) -> bool:
        """
        Restore file from backup

        Args:
            file_path: Path to file to restore
            backup_path: Path to backup file

        Returns:
            True if successful, False otherwise
        """
        try:
            if not Path(backup_path).exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            shutil.copy2(backup_path, file_path)
            logger.info(f"Restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore from backup: {str(e)}")
            return False

    def validate_file(self, file_path: str) -> bool:
        """
        Validate that file exists and is accessible

        Args:
            file_path: Path to file

        Returns:
            True if valid, False otherwise
        """
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False

        if not path.is_file():
            logger.error(f"Path is not a file: {file_path}")
            return False

        if not path.stat().st_size > 0:
            logger.error(f"File is empty: {file_path}")
            return False

        return True
