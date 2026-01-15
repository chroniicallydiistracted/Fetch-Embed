"""Factory for managing API clients"""
from typing import List, Dict, Any
from .base import BaseAPIClient, APIResult
from .google_books import GoogleBooksClient
from .openlibrary import OpenLibraryClient
from .audible import AudibleClient
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class APIClientFactory:
    """Factory for managing multiple API clients"""

    def __init__(self, config_path: str = None):
        """
        Initialize API client factory

        Args:
            config_path: Path to configuration file
        """
        self.config = get_config(config_path)
        self.clients: List[BaseAPIClient] = []
        self._initialize_clients()

    def _initialize_clients(self):
        """Initialize all enabled API clients"""
        api_config = self.config.api_config

        # Initialize Google Books if enabled
        if api_config.get('google_books', {}).get('enabled', True):
            try:
                gb_config = api_config['google_books']
                client = GoogleBooksClient(
                    api_key=gb_config.get('api_key'),
                    timeout=gb_config.get('timeout', 10),
                    max_results=gb_config.get('max_results', 5),
                    max_retries=gb_config.get('max_retries', 3),
                    rate_limit_delay=gb_config.get('rate_limit_delay', 0.1),
                    enable_cache=gb_config.get('enable_cache', True),
                    cache_ttl_hours=gb_config.get('cache_ttl_hours', 24)
                )
                self.clients.append(client)
                logger.info("Google Books API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Google Books client: {str(e)}")

        # Initialize OpenLibrary if enabled
        if api_config.get('openlibrary', {}).get('enabled', True):
            try:
                ol_config = api_config['openlibrary']
                client = OpenLibraryClient(
                    timeout=ol_config.get('timeout', 10),
                    max_results=ol_config.get('max_results', 5),
                    max_retries=ol_config.get('max_retries', 3),
                    rate_limit_delay=ol_config.get('rate_limit_delay', 1.0),
                    enable_cache=ol_config.get('enable_cache', True),
                    cache_ttl_hours=ol_config.get('cache_ttl_hours', 24)
                )
                self.clients.append(client)
                logger.info("OpenLibrary API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize OpenLibrary client: {str(e)}")

        # Initialize Audible if enabled
        if api_config.get('audible', {}).get('enabled', False):
            try:
                audible_config = api_config['audible']
                client = AudibleClient(
                    api_key=audible_config.get('api_key'),
                    timeout=audible_config.get('timeout', 10),
                    max_retries=audible_config.get('max_retries', 3),
                    rate_limit_delay=audible_config.get('rate_limit_delay', 2.0),
                    enable_cache=audible_config.get('enable_cache', True),
                    cache_ttl_hours=audible_config.get('cache_ttl_hours', 24),
                    region=audible_config.get('region', 'us')
                )
                self.clients.append(client)
                logger.info("Audible API client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Audible client: {str(e)}")

        logger.info(f"Initialized {len(self.clients)} API clients")

    def search_all(self, title: str = None, author: str = None,
                   isbn: str = None) -> Dict[str, List[APIResult]]:
        """
        Search all enabled API clients

        Args:
            title: Book title
            author: Book author
            isbn: ISBN

        Returns:
            Dictionary mapping source name to list of results
        """
        all_results = {}

        for client in self.clients:
            try:
                results = client.search(title=title, author=author, isbn=isbn)
                if results:
                    all_results[client.source_name] = results
                    logger.info(f"{client.source_name} returned {len(results)} results")
                else:
                    logger.info(f"{client.source_name} returned no results")
            except Exception as e:
                logger.error(f"Error searching {client.source_name}: {str(e)}")
                all_results[client.source_name] = []

        return all_results

    def get_all_results(self, title: str = None, author: str = None,
                        isbn: str = None) -> List[APIResult]:
        """
        Get all results from all clients as a flat list

        Args:
            title: Book title
            author: Book author
            isbn: ISBN

        Returns:
            Flat list of all results
        """
        results_by_source = self.search_all(title, author, isbn)
        all_results = []

        for source, results in results_by_source.items():
            all_results.extend(results)

        return all_results

    def close_all(self):
        """Close all API clients"""
        for client in self.clients:
            try:
                client.close()
            except Exception as e:
                logger.error(f"Error closing client {client.source_name}: {str(e)}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close_all()
