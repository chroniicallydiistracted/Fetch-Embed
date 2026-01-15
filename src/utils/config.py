"""Configuration management for Fetch-Embed"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration handler for the metadata service"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration

        Args:
            config_path: Path to YAML config file (optional)
        """
        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults"""
        default_config = {
            'api': {
                'google_books': {
                    'enabled': True,
                    'api_key': os.getenv('GOOGLE_BOOKS_API_KEY', ''),
                    'base_url': 'https://www.googleapis.com/books/v1',
                    'timeout': 10,
                    'max_results': 5,
                    'max_retries': 3,
                    'rate_limit_delay': 0.1,
                    'enable_cache': True,
                    'cache_ttl_hours': 24
                },
                'openlibrary': {
                    'enabled': True,
                    'base_url': 'https://openlibrary.org',
                    'timeout': 10,
                    'max_results': 5,
                    'max_retries': 3,
                    'rate_limit_delay': 1.0,
                    'enable_cache': True,
                    'cache_ttl_hours': 24
                },
                'audible': {
                    'enabled': False,
                    'api_key': os.getenv('AUDIBLE_API_KEY', ''),
                    'base_url': 'https://www.audible.com',
                    'timeout': 10,
                    'max_retries': 3,
                    'rate_limit_delay': 2.0,
                    'enable_cache': True,
                    'cache_ttl_hours': 24,
                    'region': 'us'
                },
                'isbndb': {
                    'enabled': False,
                    'api_key': os.getenv('ISBNDB_API_KEY', ''),
                    'base_url': 'https://api2.isbndb.com',
                    'timeout': 10
                }
            },
            'matching': {
                'title_weight': 0.4,
                'author_weight': 0.3,
                'isbn_weight': 0.3,
                'min_confidence_threshold': 0.6,
                'fuzzy_threshold': 80
            },
            'processing': {
                'backup_original': True,
                'backup_dir': '.backups',
                'supported_formats': ['.epub', '.mobi', '.azw3', '.pdf'],
                'use_filename_fallback': True,
                'overwrite_existing': True,
                'preserve_custom_fields': True
            },
            'logging': {
                'level': os.getenv('LOG_LEVEL', 'INFO'),
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'file': 'fetch_embed.log',
                'console': True
            }
        }

        # Load from file if provided
        if self.config_path and Path(self.config_path).exists():
            with open(self.config_path, 'r') as f:
                file_config = yaml.safe_load(f)
                # Merge with defaults
                default_config = self._merge_configs(default_config, file_config)

        return default_config

    def _merge_configs(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge two configuration dictionaries"""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def get(self, path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Args:
            path: Configuration path (e.g., 'api.google_books.enabled')
            default: Default value if path not found

        Returns:
            Configuration value
        """
        parts = path.split('.')
        value = self._config

        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return default

        return value

    def set(self, path: str, value: Any) -> None:
        """
        Set configuration value using dot notation

        Args:
            path: Configuration path (e.g., 'api.google_books.enabled')
            value: Value to set
        """
        parts = path.split('.')
        config = self._config

        for part in parts[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]

        config[parts[-1]] = value

    def save(self, path: str) -> None:
        """
        Save current configuration to file

        Args:
            path: Path to save configuration file
        """
        with open(path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)

    @property
    def api_config(self) -> Dict[str, Any]:
        """Get API configuration"""
        return self._config.get('api', {})

    @property
    def matching_config(self) -> Dict[str, Any]:
        """Get matching configuration"""
        return self._config.get('matching', {})

    @property
    def processing_config(self) -> Dict[str, Any]:
        """Get processing configuration"""
        return self._config.get('processing', {})

    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self._config.get('logging', {})


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get or create global configuration instance

    Args:
        config_path: Path to configuration file

    Returns:
        Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance


def reset_config() -> None:
    """Reset global configuration instance"""
    global _config_instance
    _config_instance = None
