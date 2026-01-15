"""Base API client for metadata providers"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import requests
import time
import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
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


class ResponseCache:
    """Simple file-based cache for API responses"""

    def __init__(self, cache_dir: str = ".cache/api_responses", ttl_hours: int = 24):
        """
        Initialize response cache

        Args:
            cache_dir: Directory to store cached responses
            ttl_hours: Time-to-live for cached responses in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self.enabled = True

    def _get_cache_key(self, url: str, params: Optional[Dict] = None) -> str:
        """Generate cache key from URL and parameters"""
        cache_data = f"{url}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(cache_data.encode()).hexdigest()

    def get(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Get cached response if available and not expired"""
        if not self.enabled:
            return None

        cache_key = self._get_cache_key(url, params)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            # Check if cache is still valid
            cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if cache_age > self.ttl:
                cache_file.unlink()  # Remove expired cache
                return None

            with open(cache_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.debug(f"Error reading cache: {e}")
            return None

    def set(self, url: str, params: Optional[Dict], data: Dict) -> None:
        """Store response in cache"""
        if not self.enabled:
            return

        cache_key = self._get_cache_key(url, params)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            with open(cache_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.debug(f"Error writing cache: {e}")


class BaseAPIClient(ABC):
    """Base class for metadata API clients"""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10,
                 max_retries: int = 3, rate_limit_delay: float = 0.1,
                 enable_cache: bool = True, cache_ttl_hours: int = 24):
        """
        Initialize API client

        Args:
            api_key: API key (if required)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            rate_limit_delay: Delay between requests in seconds (rate limiting)
            enable_cache: Enable response caching
            cache_ttl_hours: Cache time-to-live in hours
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.session = requests.Session()
        self.source_name = "unknown"

        # Set up proper headers
        self.session.headers.update({
            'User-Agent': 'Fetch-Embed/1.0 (Ebook Metadata Service; https://github.com/chroniicallydiistracted/Fetch-Embed)',
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate'
        })

        # Initialize cache
        self.cache = ResponseCache(ttl_hours=cache_ttl_hours)
        self.cache.enabled = enable_cache

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

    def _rate_limit(self):
        """Apply rate limiting delay"""
        if self.rate_limit_delay > 0:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make HTTP request to API with retry logic, rate limiting, and caching

        Args:
            url: Request URL
            params: Query parameters

        Returns:
            JSON response or None if request failed
        """
        # Check cache first
        cached_response = self.cache.get(url, params)
        if cached_response is not None:
            logger.debug(f"Cache hit for {url}")
            return cached_response

        # Attempt request with retries
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                # Apply rate limiting
                self._rate_limit()

                # Make request
                response = self.session.get(url, params=params, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                # Cache successful response
                self.cache.set(url, params, data)

                return data

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(f"Request timeout for {url} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.HTTPError as e:
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"Client error for {url}: {e.response.status_code}")
                    return None

                last_exception = e
                logger.warning(f"HTTP error for {url}: {str(e)} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except requests.exceptions.RequestException as e:
                last_exception = e
                logger.warning(f"Request failed for {url}: {str(e)} (attempt {attempt + 1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff

            except ValueError as e:
                logger.error(f"Invalid JSON response from {url}: {str(e)}")
                return None

        logger.error(f"All retry attempts failed for {url}: {str(last_exception)}")
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
