"""OpenLibrary API client"""
from typing import List, Optional, Dict, Any
from .base import BaseAPIClient, APIResult
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OpenLibraryClient(BaseAPIClient):
    """Client for OpenLibrary API"""

    BASE_URL = "https://openlibrary.org"

    def __init__(self, timeout: int = 10, max_results: int = 5,
                 max_retries: int = 3, rate_limit_delay: float = 1.0,
                 enable_cache: bool = True, cache_ttl_hours: int = 24):
        """
        Initialize OpenLibrary API client

        Args:
            timeout: Request timeout in seconds
            max_results: Maximum number of results to return
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay between requests (OpenLibrary recommends 1s)
            enable_cache: Enable response caching
            cache_ttl_hours: Cache TTL in hours
        """
        super().__init__(api_key=None, timeout=timeout, max_retries=max_retries,
                        rate_limit_delay=rate_limit_delay, enable_cache=enable_cache,
                        cache_ttl_hours=cache_ttl_hours)
        self.source_name = "Open Library"
        self.max_results = max_results

    def search_by_isbn(self, isbn: str) -> List[APIResult]:
        """
        Search for book by ISBN using OpenLibrary API

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            List of search results
        """
        # Clean ISBN
        clean_isbn = isbn.replace('-', '').replace(' ', '')

        # Try ISBN API endpoint first (more reliable)
        url = f"{self.BASE_URL}/isbn/{clean_isbn}.json"
        data = self._make_request(url)

        if data:
            # Get work data for more complete information
            result = self._parse_book_data(data)
            if result:
                return [result]

        # Fallback to search API
        return self._search(f"isbn:{clean_isbn}")

    def search_by_title_author(self, title: str, author: Optional[str] = None) -> List[APIResult]:
        """
        Search for book by title and author using OpenLibrary API

        Args:
            title: Book title
            author: Book author (optional)

        Returns:
            List of search results
        """
        # Build search query
        query_parts = [f'title:{title}']

        if author:
            query_parts.append(f'author:{author}')

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
        query_parts = [f'publisher:{publisher}']

        if title:
            query_parts.append(f'title:{title}')

        query = ' '.join(query_parts)
        return self._search(query)

    def get_editions_for_work(self, work_id: str, limit: int = 10) -> List[APIResult]:
        """
        Get all editions for a specific work

        Args:
            work_id: OpenLibrary work ID
            limit: Maximum number of editions to return

        Returns:
            List of edition results
        """
        if not work_id.startswith('/works/'):
            work_id = f"/works/{work_id}"

        url = f"{self.BASE_URL}{work_id}/editions.json"
        params = {'limit': limit}

        data = self._make_request(url, params)
        if not data:
            return []

        results = []
        entries = data.get('entries', [])

        logger.info(f"Found {len(entries)} editions for work {work_id}")

        for entry in entries:
            result = self._parse_book_data(entry)
            if result:
                results.append(result)

        return results

    def _search(self, query: str) -> List[APIResult]:
        """
        Execute search query using OpenLibrary Search API

        Args:
            query: Search query string

        Returns:
            List of search results
        """
        url = f"{self.BASE_URL}/search.json"

        params = {
            'q': query,
            'limit': self.max_results
        }

        data = self._make_request(url, params)

        if not data:
            return []

        results = []
        docs = data.get('docs', [])

        logger.info(f"OpenLibrary returned {len(docs)} results for query: {query}")

        for doc in docs:
            result = self._parse_search_doc(doc)
            if result:
                results.append(result)

        return results

    def _parse_search_doc(self, doc: Dict[str, Any]) -> Optional[APIResult]:
        """
        Parse search document from OpenLibrary Search API

        Args:
            doc: Document data from API

        Returns:
            APIResult object or None if parsing failed
        """
        try:
            # Extract ISBNs
            isbn = None
            isbn13 = None
            isbns = doc.get('isbn', [])

            for isbn_value in isbns:
                clean = isbn_value.replace('-', '').replace(' ', '')
                if len(clean) == 13:
                    isbn13 = clean
                    break
                elif len(clean) == 10:
                    isbn = clean

            # Extract authors
            authors = doc.get('author_name', [])

            # Extract subjects
            subjects = doc.get('subject', [])
            if subjects and len(subjects) > 10:
                # Limit to most relevant subjects
                subjects = subjects[:10]

            # Extract published date
            first_publish_year = doc.get('first_publish_year')
            published_date = str(first_publish_year) if first_publish_year else None

            # Extract publisher (use first publisher if multiple)
            publishers = doc.get('publisher', [])
            publisher = publishers[0] if publishers else None

            # Get cover image
            cover_id = doc.get('cover_i')
            thumbnail_url = None
            if cover_id:
                thumbnail_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"

            # Get edition count and use it as a quality indicator
            edition_count = doc.get('edition_count', 0)

            result = APIResult(
                title=doc.get('title'),
                authors=authors,
                isbn=isbn,
                isbn13=isbn13,
                publisher=publisher,
                published_date=published_date,
                language=doc.get('language', [None])[0] if doc.get('language') else None,
                description=None,  # Search API doesn't include description
                page_count=doc.get('number_of_pages_median'),
                subjects=subjects,
                thumbnail_url=thumbnail_url,
                preview_link=None,
                source=self.source_name,
                source_id=doc.get('key'),
                raw_data=doc
            )

            # Adjust confidence based on edition count (more editions = more reliable data)
            if edition_count > 5:
                result.confidence_score = 0.1
            elif edition_count > 0:
                result.confidence_score = 0.05

            return result

        except Exception as e:
            logger.error(f"Error parsing OpenLibrary search doc: {str(e)}")
            return None

    def _parse_book_data(self, book_data: Dict[str, Any]) -> Optional[APIResult]:
        """
        Parse book data from OpenLibrary Books API

        Args:
            book_data: Book data from API

        Returns:
            APIResult object or None if parsing failed
        """
        try:
            # Extract ISBNs
            isbn = None
            isbn13 = None

            isbn_10_list = book_data.get('isbn_10', [])
            isbn_13_list = book_data.get('isbn_13', [])

            if isbn_10_list:
                isbn = isbn_10_list[0].replace('-', '')
            if isbn_13_list:
                isbn13 = isbn_13_list[0].replace('-', '')

            # Extract authors from author references
            authors = []
            author_refs = book_data.get('authors', [])
            for author_ref in author_refs:
                if isinstance(author_ref, dict) and 'key' in author_ref:
                    # Fetch author name
                    author_key = author_ref['key']
                    author_data = self._make_request(f"{self.BASE_URL}{author_key}.json")
                    if author_data and 'name' in author_data:
                        authors.append(author_data['name'])

            # Extract publishers
            publishers = book_data.get('publishers', [])
            publisher = publishers[0] if publishers else None

            # Extract published date
            published_date = book_data.get('publish_date')

            # Extract subjects
            subjects = book_data.get('subjects', [])
            if isinstance(subjects, list) and subjects:
                subjects = [s.get('name') if isinstance(s, dict) else s for s in subjects]
                subjects = subjects[:10]  # Limit subjects

            # Get cover
            covers = book_data.get('covers', [])
            thumbnail_url = None
            if covers:
                thumbnail_url = f"https://covers.openlibrary.org/b/id/{covers[0]}-M.jpg"

            # Get description
            description = None
            if 'description' in book_data:
                desc = book_data['description']
                if isinstance(desc, dict):
                    description = desc.get('value')
                else:
                    description = desc

            # Get work information if this is an edition
            work_key = None
            if 'works' in book_data and book_data['works']:
                work_key = book_data['works'][0].get('key')

            # Extract subtitle if available
            subtitle = book_data.get('subtitle')
            full_title = book_data.get('title')
            if subtitle:
                full_title = f"{full_title}: {subtitle}"

            # Extract edition name/notes
            edition_name = book_data.get('edition_name')
            notes = book_data.get('notes')
            if isinstance(notes, dict):
                notes = notes.get('value')

            # Extract physical details
            physical_format = book_data.get('physical_format')
            weight = book_data.get('weight')

            # Extract OCLC and LCCN identifiers
            oclc_numbers = book_data.get('oclc_numbers', [])
            lccn = book_data.get('lccn', [])

            result = APIResult(
                title=full_title,
                authors=authors,
                isbn=isbn,
                isbn13=isbn13,
                publisher=publisher,
                published_date=published_date,
                language=book_data.get('languages', [{}])[0].get('key', '').split('/')[-1] if book_data.get('languages') else None,
                description=description,
                page_count=book_data.get('number_of_pages'),
                subjects=subjects if isinstance(subjects, list) else [],
                thumbnail_url=thumbnail_url,
                preview_link=None,
                source=self.source_name,
                source_id=book_data.get('key'),
                raw_data=book_data
            )

            # Add enhanced metadata
            result.raw_data['_enhanced'] = {
                'subtitle': subtitle,
                'work_key': work_key,
                'edition_name': edition_name,
                'notes': notes,
                'physical_format': physical_format,
                'weight': weight,
                'oclc_numbers': oclc_numbers,
                'lccn': lccn
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing OpenLibrary book data: {str(e)}")
            return None

    def get_work_by_id(self, work_id: str) -> Optional[APIResult]:
        """
        Get work data by OpenLibrary work ID

        Args:
            work_id: OpenLibrary work ID (e.g., "OL45883W")

        Returns:
            APIResult object or None
        """
        if not work_id.startswith('/works/'):
            work_id = f"/works/{work_id}"

        url = f"{self.BASE_URL}{work_id}.json"
        data = self._make_request(url)

        if data:
            return self._parse_book_data(data)

        return None
