"""Base metadata extractor"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime


@dataclass
class EbookMetadata:
    """Container for ebook metadata"""

    # Core metadata
    title: Optional[str] = None
    authors: List[str] = field(default_factory=list)
    isbn: Optional[str] = None
    isbn13: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None

    # Additional metadata
    subjects: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    series: Optional[str] = None
    series_index: Optional[int] = None
    pages: Optional[int] = None
    rating: Optional[float] = None

    # File information
    file_path: Optional[str] = None
    file_format: Optional[str] = None
    file_size: Optional[int] = None

    # Metadata quality indicators
    has_isbn: bool = False
    metadata_completeness: float = 0.0

    # Custom fields
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Post-initialization processing"""
        # Ensure authors is a list
        if isinstance(self.authors, str):
            self.authors = [self.authors]

        # Check if ISBN exists
        self.has_isbn = bool(self.isbn or self.isbn13)

        # Calculate metadata completeness
        self._calculate_completeness()

    def _calculate_completeness(self) -> None:
        """Calculate metadata completeness score (0-1)"""
        core_fields = ['title', 'authors', 'isbn', 'publisher', 'published_date']
        filled_fields = sum(1 for field in core_fields if getattr(self, field))
        self.metadata_completeness = filled_fields / len(core_fields)

    def is_metadata_quality_good(self) -> bool:
        """Check if metadata quality is acceptable"""
        return self.metadata_completeness >= 0.6

    def to_dict(self) -> Dict[str, Any]:
        """Convert metadata to dictionary"""
        return {
            'title': self.title,
            'authors': self.authors,
            'isbn': self.isbn,
            'isbn13': self.isbn13,
            'publisher': self.publisher,
            'published_date': self.published_date,
            'language': self.language,
            'description': self.description,
            'subjects': self.subjects,
            'tags': self.tags,
            'series': self.series,
            'series_index': self.series_index,
            'pages': self.pages,
            'rating': self.rating,
            'file_path': self.file_path,
            'file_format': self.file_format,
            'file_size': self.file_size,
            'has_isbn': self.has_isbn,
            'metadata_completeness': self.metadata_completeness,
            'custom_fields': self.custom_fields
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EbookMetadata':
        """Create metadata from dictionary"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class BaseExtractor(ABC):
    """Base class for metadata extractors"""

    def __init__(self):
        """Initialize extractor"""
        self.supported_formats: List[str] = []

    @abstractmethod
    def can_handle(self, file_path: str) -> bool:
        """
        Check if extractor can handle the given file

        Args:
            file_path: Path to ebook file

        Returns:
            True if extractor can handle the file
        """
        pass

    @abstractmethod
    def extract(self, file_path: str) -> EbookMetadata:
        """
        Extract metadata from ebook file

        Args:
            file_path: Path to ebook file

        Returns:
            Extracted metadata
        """
        pass

    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic file information

        Args:
            file_path: Path to file

        Returns:
            File information dictionary
        """
        path = Path(file_path)
        return {
            'file_path': str(path.absolute()),
            'file_format': path.suffix.lower(),
            'file_size': path.stat().st_size if path.exists() else 0
        }

    def _extract_filename_metadata(self, file_path: str) -> Dict[str, str]:
        """
        Extract potential metadata from filename

        Args:
            file_path: Path to file

        Returns:
            Dictionary with potential title and author
        """
        filename = Path(file_path).stem

        # Common patterns:
        # "Title - Author.epub"
        # "Author - Title.epub"
        # "Title (Year).epub"

        result = {'title': '', 'author': ''}

        # Remove year in parentheses
        import re
        filename = re.sub(r'\s*\(\d{4}\)\s*', ' ', filename)

        # Try to split by common separators
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            # Heuristic: longer part is usually the title
            if len(parts[0]) > len(parts[1]):
                result['title'] = parts[0].strip()
                result['author'] = parts[1].strip()
            else:
                result['author'] = parts[0].strip()
                result['title'] = parts[1].strip()
        else:
            # Use whole filename as title
            result['title'] = filename.strip()

        return result
