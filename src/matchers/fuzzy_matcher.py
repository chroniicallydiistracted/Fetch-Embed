"""Fuzzy matching utilities for comparing metadata"""
from typing import Optional, List
from rapidfuzz import fuzz, process
from ..utils.logger import get_logger

logger = get_logger(__name__)


class FuzzyMatcher:
    """Fuzzy string matching utilities"""

    def __init__(self, threshold: int = 80):
        """
        Initialize fuzzy matcher

        Args:
            threshold: Minimum similarity score (0-100) to consider a match
        """
        self.threshold = threshold

    def compare_strings(self, str1: Optional[str], str2: Optional[str],
                       method: str = 'token_sort_ratio') -> float:
        """
        Compare two strings and return similarity score

        Args:
            str1: First string
            str2: Second string
            method: Comparison method ('ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio')

        Returns:
            Similarity score (0-100)
        """
        if not str1 or not str2:
            return 0.0

        # Normalize strings
        str1 = self._normalize(str1)
        str2 = self._normalize(str2)

        # Choose comparison method
        if method == 'ratio':
            score = fuzz.ratio(str1, str2)
        elif method == 'partial_ratio':
            score = fuzz.partial_ratio(str1, str2)
        elif method == 'token_sort_ratio':
            score = fuzz.token_sort_ratio(str1, str2)
        elif method == 'token_set_ratio':
            score = fuzz.token_set_ratio(str1, str2)
        else:
            score = fuzz.ratio(str1, str2)

        return float(score)

    def compare_titles(self, title1: Optional[str], title2: Optional[str]) -> float:
        """
        Compare two book titles with title-specific logic

        Args:
            title1: First title
            title2: Second title

        Returns:
            Similarity score (0-100)
        """
        if not title1 or not title2:
            return 0.0

        # Remove common subtitles and edition info
        title1_clean = self._clean_title(title1)
        title2_clean = self._clean_title(title2)

        # Use token_sort_ratio for better handling of word order differences
        score = self.compare_strings(title1_clean, title2_clean, method='token_sort_ratio')

        # Boost score if titles are very similar but not exact
        if score > 85:
            # Check partial match for subtitle differences
            partial_score = fuzz.partial_ratio(title1_clean, title2_clean)
            score = max(score, partial_score)

        return score

    def compare_authors(self, authors1: Optional[List[str]], authors2: Optional[List[str]]) -> float:
        """
        Compare two lists of authors

        Args:
            authors1: First author list
            authors2: Second author list

        Returns:
            Similarity score (0-100)
        """
        if not authors1 or not authors2:
            return 0.0

        # Handle single author vs list
        if isinstance(authors1, str):
            authors1 = [authors1]
        if isinstance(authors2, str):
            authors2 = [authors2]

        # If both have authors, find best matches
        max_score = 0.0

        for author1 in authors1:
            for author2 in authors2:
                # Compare full names
                score = self._compare_author_names(author1, author2)
                max_score = max(max_score, score)

        return max_score

    def _compare_author_names(self, name1: str, name2: str) -> float:
        """
        Compare two author names with name-specific logic

        Args:
            name1: First author name
            name2: Second author name

        Returns:
            Similarity score (0-100)
        """
        if not name1 or not name2:
            return 0.0

        # Normalize names
        name1 = self._normalize(name1)
        name2 = self._normalize(name2)

        # Try different comparison strategies
        scores = []

        # Full name comparison
        scores.append(fuzz.ratio(name1, name2))

        # Token sort (handles "John Smith" vs "Smith, John")
        scores.append(fuzz.token_sort_ratio(name1, name2))

        # Check if one name is contained in the other (handles initials)
        if len(name1) < len(name2):
            scores.append(fuzz.partial_ratio(name1, name2))
        else:
            scores.append(fuzz.partial_ratio(name2, name1))

        return max(scores)

    def compare_isbns(self, isbn1: Optional[str], isbn2: Optional[str]) -> float:
        """
        Compare two ISBNs (exact match only)

        Args:
            isbn1: First ISBN
            isbn2: Second ISBN

        Returns:
            100.0 if exact match, 0.0 otherwise
        """
        if not isbn1 or not isbn2:
            return 0.0

        # Clean ISBNs
        clean1 = isbn1.replace('-', '').replace(' ', '').upper()
        clean2 = isbn2.replace('-', '').replace(' ', '').upper()

        # Exact match only for ISBNs
        return 100.0 if clean1 == clean2 else 0.0

    def find_best_match(self, query: str, choices: List[str],
                       method: str = 'token_sort_ratio') -> Optional[tuple]:
        """
        Find best match from a list of choices

        Args:
            query: Query string
            choices: List of choice strings
            method: Comparison method

        Returns:
            Tuple of (best_match, score, index) or None
        """
        if not query or not choices:
            return None

        query_clean = self._normalize(query)
        choices_clean = [self._normalize(c) for c in choices]

        # Use process.extractOne for efficiency
        scorer = getattr(fuzz, method, fuzz.token_sort_ratio)
        result = process.extractOne(query_clean, choices_clean, scorer=scorer)

        if result and result[1] >= self.threshold:
            # Return original choice (not normalized)
            index = choices_clean.index(result[0])
            return (choices[index], result[1], index)

        return None

    def is_match(self, str1: Optional[str], str2: Optional[str],
                method: str = 'token_sort_ratio') -> bool:
        """
        Check if two strings match above threshold

        Args:
            str1: First string
            str2: Second string
            method: Comparison method

        Returns:
            True if match, False otherwise
        """
        score = self.compare_strings(str1, str2, method)
        return score >= self.threshold

    def _normalize(self, text: str) -> str:
        """
        Normalize text for comparison

        Args:
            text: Input text

        Returns:
            Normalized text
        """
        if not text:
            return ""

        # Convert to lowercase
        text = text.lower()

        # Remove extra whitespace
        text = ' '.join(text.split())

        return text.strip()

    def _clean_title(self, title: str) -> str:
        """
        Clean title for comparison (remove edition info, etc.)

        Args:
            title: Book title

        Returns:
            Cleaned title
        """
        import re

        if not title:
            return ""

        # Remove content in parentheses (often edition info)
        title = re.sub(r'\([^)]*\)', '', title)

        # Remove content in square brackets
        title = re.sub(r'\[[^\]]*\]', '', title)

        # Remove common edition markers
        edition_patterns = [
            r'\d+(?:st|nd|rd|th)\s+edition',
            r'revised\s+edition',
            r'kindle\s+edition',
            r'paperback',
            r'hardcover',
        ]

        for pattern in edition_patterns:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # Clean up
        title = ' '.join(title.split())

        return title.strip()
