"""Google Books API client"""
from typing import List, Optional, Dict, Any
from .base import BaseAPIClient, APIResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


class GoogleBooksClient(BaseAPIClient):
    """Client for Google Books API v1"""

    BASE_URL = "https://www.googleapis.com/books/v1"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10, max_results: int = 5,
                 max_retries: int = 3, rate_limit_delay: float = 0.1,
                 enable_cache: bool = True, cache_ttl_hours: int = 24):
        """
        Initialize Google Books API client

        Args:
            api_key: Google Books API key (optional but recommended for higher rate limits)
            timeout: Request timeout in seconds
            max_results: Maximum number of results to return
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay between requests in seconds
            enable_cache: Enable response caching
            cache_ttl_hours: Cache TTL in hours
        """
        super().__init__(api_key, timeout, max_retries, rate_limit_delay, enable_cache, cache_ttl_hours)
        self.source_name = "Google Books"
        self.max_results = min(max_results, 40)  # Google Books API max is 40

    def search_by_isbn(self, isbn: str) -> List[APIResult]:
        """
        Search for book by ISBN using Google Books API

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            List of search results
        """
        # Clean ISBN
        clean_isbn = isbn.replace('-', '').replace(' ', '')

        # Search by ISBN identifier
        query = f"isbn:{clean_isbn}"
        return self._search(query)

    def search_by_title_author(self, title: str, author: Optional[str] = None) -> List[APIResult]:
        """
        Search for book by title and author using Google Books API

        Args:
            title: Book title
            author: Book author (optional)

        Returns:
            List of search results
        """
        # Build search query
        query_parts = [f'intitle:"{title}"']

        if author:
            query_parts.append(f'inauthor:"{author}"')

        query = ' '.join(query_parts)
        return self._search(query)

    def search_by_publisher(self, publisher: str, title: Optional[str] = None) -> List[APIResult]:
        """
        Search for books by publisher

        Args:
            publisher: Publisher name
            title: Optional title filter

        Returns:
            List of search results
        """
        query_parts = [f'inpublisher:"{publisher}"']

        if title:
            query_parts.append(f'intitle:"{title}"')

        query = ' '.join(query_parts)
        return self._search(query)

    def search_by_subject(self, subject: str) -> List[APIResult]:
        """
        Search for books by subject/category

        Args:
            subject: Subject or category

        Returns:
            List of search results
        """
        query = f'subject:"{subject}"'
        return self._search(query)

    def _search(self, query: str) -> List[APIResult]:
        """
        Execute search query

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        url = f"{self.BASE_URL}/volumes"

        params = {
            'q': query,
            'maxResults': self.max_results,
            'printType': 'books'
        }

        if self.api_key:
            params['key'] = self.api_key

        data = self._make_request(url, params)

        if not data:
            return []

        results = []
        items = data.get('items', [])

        logger.info(f"Google Books returned {len(items)} results for query: {query}")

        for item in items:
            result = self._parse_volume(item)
            if result:
                results.append(result)

        return results

    def _parse_volume(self, volume_data: Dict[str, Any]) -> Optional[APIResult]:
        """
        Parse volume data from Google Books API

        Args:
            volume_data: Volume data from API

        Returns:
            APIResult object or None if parsing failed
        """
        try:
            volume_info = volume_data.get('volumeInfo', {})

            # Extract industry identifiers (ISBN)
            isbn = None
            isbn13 = None
            identifiers = volume_info.get('industryIdentifiers', [])
            for identifier in identifiers:
                id_type = identifier.get('type', '')
                id_value = identifier.get('identifier', '')

                if id_type == 'ISBN_13':
                    isbn13 = id_value.replace('-', '')
                elif id_type == 'ISBN_10':
                    isbn = id_value.replace('-', '')

            # Extract published date
            published_date = volume_info.get('publishedDate')

            # Extract authors
            authors = volume_info.get('authors', [])

            # Extract subjects/categories
            subjects = volume_info.get('categories', [])

            # Extract thumbnail (prefer larger images)
            image_links = volume_info.get('imageLinks', {})
            thumbnail_url = (
                image_links.get('large') or
                image_links.get('medium') or
                image_links.get('thumbnail') or
                image_links.get('smallThumbnail')
            )

            # Extract subtitle if available
            subtitle = volume_info.get('subtitle')
            full_title = volume_info.get('title')
            if subtitle:
                full_title = f"{full_title}: {subtitle}"

            # Extract maturity rating and content version
            maturity_rating = volume_info.get('maturityRating')
            content_version = volume_info.get('contentVersion')

            # Extract print type (BOOK or MAGAZINE)
            print_type = volume_info.get('printType')

            # Extract average rating and ratings count
            average_rating = volume_info.get('averageRating')
            ratings_count = volume_info.get('ratingsCount')

            result = APIResult(
                title=full_title,
                authors=authors,
                isbn=isbn,
                isbn13=isbn13,
                publisher=volume_info.get('publisher'),
                published_date=published_date,
                language=volume_info.get('language'),
                description=volume_info.get('description'),
                page_count=volume_info.get('pageCount'),
                subjects=subjects,
                thumbnail_url=thumbnail_url,
                preview_link=volume_info.get('previewLink'),
                source=self.source_name,
                source_id=volume_data.get('id'),
                raw_data=volume_data
            )

            # Add additional metadata to raw_data for potential future use
            result.raw_data['_enhanced'] = {
                'subtitle': subtitle,
                'maturity_rating': maturity_rating,
                'content_version': content_version,
                'print_type': print_type,
                'average_rating': average_rating,
                'ratings_count': ratings_count
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing Google Books volume data: {str(e)}")
            return None

    def get_volume_by_id(self, volume_id: str) -> Optional[APIResult]:
        """
        Get specific volume by ID

        Args:
            volume_id: Google Books volume ID

        Returns:
            APIResult object or None
        """
        url = f"{self.BASE_URL}/volumes/{volume_id}"

        params = {}
        if self.api_key:
            params['key'] = self.api_key

        data = self._make_request(url, params)

        if data:
            return self._parse_volume(data)

        return None
