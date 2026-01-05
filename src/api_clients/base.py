"""Base API client for metadata providers"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import requests
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class APIResult:
    """Container for API search result"""

    # Core metadata
    title: Optional[str] = None
    authors: List[str] = None
    isbn: Optional[str] = None
    isbn13: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    language: Optional[str] = None
    description: Optional[str] = None
    page_count: Optional[int] = None

    # Additional data
    subjects: List[str] = None
    thumbnail_url: Optional[str] = None
    preview_link: Optional[str] = None

    # Source information
    source: Optional[str] = None
    source_id: Optional[str] = None
    confidence_score: float = 0.0

    # Raw data from API
    raw_data: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values"""
        if self.authors is None:
            self.authors = []
        if self.subjects is None:
            self.subjects = []
        if self.raw_data is None:
            self.raw_data = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'title': self.title,
            'authors': self.authors,
            'isbn': self.isbn,
            'isbn13': self.isbn13,
            'publisher': self.publisher,
            'published_date': self.published_date,
            'language': self.language,
            'description': self.description,
            'page_count': self.page_count,
            'subjects': self.subjects,
            'thumbnail_url': self.thumbnail_url,
            'preview_link': self.preview_link,
            'source': self.source,
            'source_id': self.source_id,
            'confidence_score': self.confidence_score
        }


class BaseAPIClient(ABC):
    """Base class for metadata API clients"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        """
        Initialize API client

        Args:
            api_key: API key (if required)
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.source_name = "unknown"

    @abstractmethod
    def search_by_isbn(self, isbn: str) -> List[APIResult]:
        """
        Search for book by ISBN

        Args:
            isbn: ISBN to search for

        Returns:
            List of search results
        """
        pass

    @abstractmethod
    def search_by_title_author(self, title: str, author: Optional[str] = None) -> List[APIResult]:
        """
        Search for book by title and optionally author

        Args:
            title: Book title
            author: Book author (optional)

        Returns:
            List of search results
        """
        pass

    def search(self, title: Optional[str] = None, author: Optional[str] = None,
               isbn: Optional[str] = None) -> List[APIResult]:
        """
        Generic search method that routes to appropriate search method

        Args:
            title: Book title
            author: Book author
            isbn: ISBN

        Returns:
            List of search results
        """
        results = []

        # Prefer ISBN search if available
        if isbn:
            logger.info(f"Searching {self.source_name} by ISBN: {isbn}")
            results = self.search_by_isbn(isbn)

        # Fall back to title/author search
        if not results and title:
            logger.info(f"Searching {self.source_name} by title/author: {title} / {author}")
            results = self.search_by_title_author(title, author)

        # Set source for all results
        for result in results:
            result.source = self.source_name

        return results

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to API

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            JSON response or None if request failed
        """
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout for {url}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {str(e)}")
        except ValueError as e:
            logger.error(f"Invalid JSON response from {url}: {str(e)}")

        return None

    def close(self):
        """Close the session"""
        self.session.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
