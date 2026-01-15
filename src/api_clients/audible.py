"""Audible metadata client for audiobook metadata extraction"""
from typing import List, Optional, Dict, Any
from .base import BaseAPIClient, APIResult
from ..utils.logger import get_logger
import re

logger = get_logger(__name__)


class AudibleClient(BaseAPIClient):
    """
    Client for Audible audiobook metadata

    Note: Audible does not have an official public API. This client provides:
    1. ASIN-based metadata extraction from Audible files
    2. Integration with Amazon Product Advertising API (if configured)
    3. Basic web scraping capabilities (use responsibly and respect robots.txt)
    """

    BASE_URL = "https://www.audible.com"

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10,
                 max_retries: int = 3, rate_limit_delay: float = 2.0,
                 enable_cache: bool = True, cache_ttl_hours: int = 24,
                 region: str = "us"):
        """
        Initialize Audible client

        Args:
            api_key: Amazon Product Advertising API key (optional)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            rate_limit_delay: Delay between requests (Audible prefers 2s+)
            enable_cache: Enable response caching
            cache_ttl_hours: Cache TTL in hours
            region: Audible region (us, uk, de, fr, etc.)
        """
        super().__init__(api_key, timeout, max_retries, rate_limit_delay, enable_cache, cache_ttl_hours)
        self.source_name = "Audible"
        self.region = region.lower()

        # Set region-specific base URL
        if self.region == "us":
            self.BASE_URL = "https://www.audible.com"
        elif self.region == "uk":
            self.BASE_URL = "https://www.audible.co.uk"
        elif self.region == "de":
            self.BASE_URL = "https://www.audible.de"
        elif self.region == "fr":
            self.BASE_URL = "https://www.audible.fr"
        else:
            self.BASE_URL = f"https://www.audible.{self.region}"

    def search_by_isbn(self, isbn: str) -> List[APIResult]:
        """
        Search for audiobook by ISBN

        Note: Audible audiobooks typically don't use ISBNs, but companion print books do.
        This method will attempt to find the audiobook version.

        Args:
            isbn: ISBN of the print book

        Returns:
            List of search results (may be empty)
        """
        logger.info(f"Audible: ISBN search not directly supported. Use ASIN or title/author search.")
        return []

    def search_by_title_author(self, title: str, author: Optional[str] = None) -> List[APIResult]:
        """
        Search for audiobook by title and author

        Note: This requires web scraping and should be used sparingly.
        Consider using official Amazon Product Advertising API instead.

        Args:
            title: Book title
            author: Book author (optional)

        Returns:
            List of search results
        """
        logger.info(f"Audible: Title/author search requires web scraping or Amazon PA API")
        logger.info(f"Searching for: '{title}' by '{author}'")

        # Construct search query
        query_parts = [title]
        if author:
            query_parts.append(author)
        query = ' '.join(query_parts)

        # Use search endpoint
        url = f"{self.BASE_URL}/search"
        params = {
            'keywords': query,
            'feature_six_browse-bin': '18573211011'  # Audiobooks category (US)
        }

        data = self._make_request(url, params)

        if not data:
            logger.warning("Audible search failed or returned no data")
            return []

        # Note: Actual parsing would require HTML parsing
        # For production use, implement proper HTML parsing with BeautifulSoup
        logger.info("Audible search requires HTML parsing - not implemented in basic version")
        return []

    def search_by_asin(self, asin: str) -> List[APIResult]:
        """
        Search for audiobook by ASIN (Amazon Standard Identification Number)

        ASINs are the primary identifier for Audible audiobooks.

        Args:
            asin: Amazon/Audible ASIN

        Returns:
            List with single result if found
        """
        logger.info(f"Searching Audible by ASIN: {asin}")

        # Clean ASIN
        clean_asin = asin.strip().upper()

        if not self._validate_asin(clean_asin):
            logger.error(f"Invalid ASIN format: {asin}")
            return []

        # Construct product URL
        url = f"{self.BASE_URL}/pd/{clean_asin}"

        # Note: This would require HTML parsing in production
        logger.info(f"ASIN lookup URL: {url}")
        logger.info("ASIN lookup requires HTML parsing or Amazon PA API - not implemented in basic version")

        return []

    def _validate_asin(self, asin: str) -> bool:
        """
        Validate ASIN format

        Args:
            asin: ASIN to validate

        Returns:
            True if valid ASIN format
        """
        # ASINs are typically 10 characters, alphanumeric
        pattern = r'^[A-Z0-9]{10}$'
        return bool(re.match(pattern, asin))

    def extract_metadata_from_file(self, file_path: str) -> Optional[APIResult]:
        """
        Extract metadata from Audible audiobook file (.aax, .aa, .aaxc)

        This uses ffprobe or similar tools to extract embedded metadata.

        Args:
            file_path: Path to Audible audiobook file

        Returns:
            APIResult with extracted metadata or None
        """
        logger.info(f"Extracting Audible metadata from file: {file_path}")

        # This would require:
        # 1. ffprobe to extract metadata
        # 2. Parsing of Audible-specific tags
        # 3. ASIN extraction from metadata or filename

        logger.info("File metadata extraction requires ffprobe integration - not implemented in basic version")
        logger.info("For production use, install ffprobe and implement metadata extraction")

        return None

    def get_book_details(self, asin: str, include_series: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get detailed book information by ASIN

        Args:
            asin: Audible ASIN
            include_series: Whether to include series information

        Returns:
            Dictionary with book details or None
        """
        logger.info(f"Getting Audible book details for ASIN: {asin}")

        # This would require Amazon Product Advertising API or web scraping
        logger.info("Book details require Amazon PA API - not implemented in basic version")

        return None


# Helper function to extract ASIN from various sources
def extract_asin_from_text(text: str) -> Optional[str]:
    """
    Extract ASIN from text (URL, filename, metadata, etc.)

    Args:
        text: Text to search for ASIN

    Returns:
        ASIN if found, None otherwise
    """
    # Look for ASIN patterns in text
    # ASINs in URLs: /dp/ASIN or /pd/ASIN
    url_pattern = r'/(?:dp|pd)/([A-Z0-9]{10})'
    match = re.search(url_pattern, text)
    if match:
        return match.group(1)

    # Look for standalone ASIN pattern
    asin_pattern = r'\b([A-Z0-9]{10})\b'
    match = re.search(asin_pattern, text)
    if match:
        potential_asin = match.group(1)
        # Verify it looks like a valid ASIN (at least one letter)
        if re.search(r'[A-Z]', potential_asin):
            return potential_asin

    return None


# Note about Audible API usage:
# =================================
# Audible does not provide an official public API. There are several alternatives:
#
# 1. Amazon Product Advertising API:
#    - Official API from Amazon
#    - Requires approval and API keys
#    - Can query Audible products via ASIN
#    - URL: https://webservices.amazon.com/paapi5/documentation/
#
# 2. Unofficial audible-cli tools:
#    - Community-maintained CLI tools
#    - Require Audible account credentials
#    - Can extract metadata from your library
#    - Use at your own risk, may violate ToS
#
# 3. File metadata extraction:
#    - Audible files (.aax, .aa) contain embedded metadata
#    - Use ffprobe or similar tools to extract
#    - No API calls needed, works offline
#
# 4. Web scraping:
#    - Parse Audible website HTML
#    - Respect robots.txt and rate limits
#    - Fragile (breaks when website changes)
#    - May violate Terms of Service
#
# For production use, we recommend:
# - Option 1 (Amazon PA API) for legitimate commercial use
# - Option 3 (file metadata) for personal library management
