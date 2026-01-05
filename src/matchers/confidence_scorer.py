"""Confidence scoring and result aggregation"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from collections import Counter
from ..api_clients.base import APIResult
from ..extractors.base import EbookMetadata
from .fuzzy_matcher import FuzzyMatcher
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoredMetadata:
    """Metadata with confidence scores for each field"""

    title: Optional[str] = None
    title_score: float = 0.0

    authors: List[str] = None
    authors_score: float = 0.0

    isbn: Optional[str] = None
    isbn_score: float = 0.0

    isbn13: Optional[str] = None
    isbn13_score: float = 0.0

    publisher: Optional[str] = None
    publisher_score: float = 0.0

    published_date: Optional[str] = None
    published_date_score: float = 0.0

    language: Optional[str] = None
    language_score: float = 0.0

    description: Optional[str] = None
    description_score: float = 0.0

    page_count: Optional[int] = None
    page_count_score: float = 0.0

    subjects: List[str] = None
    subjects_score: float = 0.0

    # Overall confidence
    overall_confidence: float = 0.0

    # Source attribution
    sources: Dict[str, Any] = None

    def __post_init__(self):
        """Initialize default values"""
        if self.authors is None:
            self.authors = []
        if self.subjects is None:
            self.subjects = []
        if self.sources is None:
            self.sources = {}

    def to_ebook_metadata(self, original_metadata: EbookMetadata) -> EbookMetadata:
        """
        Convert to EbookMetadata, preserving file information

        Args:
            original_metadata: Original metadata from file

        Returns:
            EbookMetadata with scored values
        """
        metadata = EbookMetadata(
            title=self.title or original_metadata.title,
            authors=self.authors or original_metadata.authors,
            isbn=self.isbn or original_metadata.isbn,
            isbn13=self.isbn13 or original_metadata.isbn13,
            publisher=self.publisher or original_metadata.publisher,
            published_date=self.published_date or original_metadata.published_date,
            language=self.language or original_metadata.language,
            description=self.description or original_metadata.description,
            subjects=self.subjects or original_metadata.subjects,
            pages=self.page_count or original_metadata.pages,
            file_path=original_metadata.file_path,
            file_format=original_metadata.file_format,
            file_size=original_metadata.file_size,
            custom_fields=original_metadata.custom_fields
        )

        return metadata


class ConfidenceScorer:
    """Score and aggregate metadata from multiple sources"""

    def __init__(self, config_path: str = None):
        """
        Initialize confidence scorer

        Args:
            config_path: Path to configuration file
        """
        self.config = get_config(config_path)
        self.matcher = FuzzyMatcher(
            threshold=self.config.get('matching.fuzzy_threshold', 80)
        )

        # Weights for different metadata fields
        self.weights = {
            'title': self.config.get('matching.title_weight', 0.4),
            'author': self.config.get('matching.author_weight', 0.3),
            'isbn': self.config.get('matching.isbn_weight', 0.3)
        }

        self.min_confidence = self.config.get('matching.min_confidence_threshold', 0.6)

    def score_results(self, original_metadata: EbookMetadata,
                     api_results: List[APIResult]) -> ScoredMetadata:
        """
        Score API results against original metadata and aggregate best values

        Args:
            original_metadata: Original metadata from file
            api_results: List of results from API clients

        Returns:
            ScoredMetadata with best values and confidence scores
        """
        if not api_results:
            logger.warning("No API results to score")
            return self._create_fallback_metadata(original_metadata)

        # Score each API result against original metadata
        scored_results = []
        for result in api_results:
            score = self._calculate_match_score(original_metadata, result)
            result.confidence_score = score
            scored_results.append(result)

        # Sort by confidence score
        scored_results.sort(key=lambda x: x.confidence_score, reverse=True)

        # Log top results
        logger.info(f"Top 3 API results by confidence:")
        for i, result in enumerate(scored_results[:3], 1):
            logger.info(f"  {i}. {result.source}: {result.title} - {result.confidence_score:.2%}")

        # Aggregate best metadata from all results
        best_metadata = self._aggregate_metadata(original_metadata, scored_results)

        return best_metadata

    def _calculate_match_score(self, original: EbookMetadata, api_result: APIResult) -> float:
        """
        Calculate match score between original metadata and API result

        Args:
            original: Original metadata
            api_result: API result

        Returns:
            Match score (0-1)
        """
        scores = []
        weights = []

        # Title matching
        if original.title and api_result.title:
            title_score = self.matcher.compare_titles(original.title, api_result.title) / 100.0
            scores.append(title_score)
            weights.append(self.weights['title'])
        elif api_result.title:  # API has title but original doesn't
            scores.append(0.5)  # Moderate score for having data
            weights.append(self.weights['title'])

        # Author matching
        if original.authors and api_result.authors:
            author_score = self.matcher.compare_authors(original.authors, api_result.authors) / 100.0
            scores.append(author_score)
            weights.append(self.weights['author'])
        elif api_result.authors:  # API has authors but original doesn't
            scores.append(0.5)
            weights.append(self.weights['author'])

        # ISBN matching (exact match is very strong signal)
        isbn_match = False
        if original.isbn or original.isbn13:
            if original.isbn and api_result.isbn:
                isbn_score = self.matcher.compare_isbns(original.isbn, api_result.isbn) / 100.0
                if isbn_score == 1.0:
                    isbn_match = True
                scores.append(isbn_score)
                weights.append(self.weights['isbn'])
            elif original.isbn13 and api_result.isbn13:
                isbn_score = self.matcher.compare_isbns(original.isbn13, api_result.isbn13) / 100.0
                if isbn_score == 1.0:
                    isbn_match = True
                scores.append(isbn_score)
                weights.append(self.weights['isbn'])
        elif api_result.isbn or api_result.isbn13:  # API has ISBN but original doesn't
            scores.append(0.5)
            weights.append(self.weights['isbn'])

        # Calculate weighted average
        if not scores:
            return 0.0

        weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)

        # Boost score if ISBN matches exactly
        if isbn_match:
            weighted_score = min(1.0, weighted_score * 1.2)

        return weighted_score

    def _aggregate_metadata(self, original: EbookMetadata,
                           scored_results: List[APIResult]) -> ScoredMetadata:
        """
        Aggregate best metadata from scored results

        Args:
            original: Original metadata
            scored_results: List of scored API results (sorted by confidence)

        Returns:
            Aggregated metadata with confidence scores
        """
        metadata = ScoredMetadata()

        # Filter results by minimum confidence
        good_results = [r for r in scored_results if r.confidence_score >= self.min_confidence]

        if not good_results:
            logger.warning(f"No results above confidence threshold ({self.min_confidence:.2%}), using best available")
            good_results = scored_results[:3] if len(scored_results) >= 3 else scored_results

        # Title: Use highest confidence result with title
        metadata.title, metadata.title_score = self._select_best_field(
            good_results, 'title', original.title
        )

        # Authors: Use highest confidence result with authors
        metadata.authors, metadata.authors_score = self._select_best_field(
            good_results, 'authors', original.authors
        )

        # ISBN: Prefer results with matching ISBN, or highest confidence
        metadata.isbn, metadata.isbn_score = self._select_best_field(
            good_results, 'isbn', original.isbn
        )

        # ISBN-13: Prefer results with matching ISBN-13, or highest confidence
        metadata.isbn13, metadata.isbn13_score = self._select_best_field(
            good_results, 'isbn13', original.isbn13
        )

        # Publisher: Use consensus or highest confidence
        metadata.publisher, metadata.publisher_score = self._select_best_field(
            good_results, 'publisher', original.publisher, use_consensus=True
        )

        # Published date: Use consensus or highest confidence
        metadata.published_date, metadata.published_date_score = self._select_best_field(
            good_results, 'published_date', original.published_date, use_consensus=True
        )

        # Language: Use consensus
        metadata.language, metadata.language_score = self._select_best_field(
            good_results, 'language', original.language, use_consensus=True
        )

        # Description: Use longest/most detailed from high confidence results
        metadata.description, metadata.description_score = self._select_best_description(
            good_results, original.description
        )

        # Page count: Use consensus
        metadata.page_count, metadata.page_count_score = self._select_best_field(
            good_results, 'page_count', original.pages, use_consensus=True
        )

        # Subjects: Aggregate from multiple sources
        metadata.subjects, metadata.subjects_score = self._aggregate_subjects(good_results)

        # Calculate overall confidence
        metadata.overall_confidence = self._calculate_overall_confidence(metadata, scored_results)

        # Track sources
        metadata.sources = {
            result.source: result.confidence_score
            for result in good_results[:5]  # Top 5 sources
        }

        logger.info(f"Aggregated metadata with overall confidence: {metadata.overall_confidence:.2%}")

        return metadata

    def _select_best_field(self, results: List[APIResult], field_name: str,
                          original_value: Any, use_consensus: bool = False) -> tuple:
        """
        Select best value for a metadata field

        Args:
            results: List of API results
            field_name: Name of field to select
            original_value: Original value from file
            use_consensus: Whether to use consensus voting

        Returns:
            Tuple of (best_value, confidence_score)
        """
        values = []
        for result in results:
            value = getattr(result, field_name, None)
            if value:
                if isinstance(value, list) and not value:  # Empty list
                    continue
                values.append((value, result.confidence_score))

        if not values:
            return (original_value, 0.0)

        if use_consensus and len(values) > 1:
            # Use voting for consensus
            value_counts = Counter()
            value_scores = {}

            for value, score in values:
                # Normalize value for comparison
                key = str(value).lower().strip() if value else ""
                if key:
                    value_counts[key] += score  # Weight by confidence
                    if key not in value_scores or score > value_scores[key]:
                        value_scores[key] = score

            if value_counts:
                # Get most common value
                most_common_key = value_counts.most_common(1)[0][0]
                # Find original value that matches
                for value, score in values:
                    if str(value).lower().strip() == most_common_key:
                        return (value, value_scores[most_common_key])

        # Use highest confidence result
        values.sort(key=lambda x: x[1], reverse=True)
        return values[0]

    def _select_best_description(self, results: List[APIResult],
                                 original_description: Optional[str]) -> tuple:
        """
        Select best description (longest from high confidence results)

        Args:
            results: List of API results
            original_description: Original description

        Returns:
            Tuple of (best_description, confidence_score)
        """
        descriptions = []
        for result in results:
            if result.description and len(result.description) > 50:  # Min length
                descriptions.append((result.description, result.confidence_score))

        if not descriptions:
            return (original_description, 0.0)

        # Sort by length and confidence
        descriptions.sort(key=lambda x: (len(x[0]), x[1]), reverse=True)
        return descriptions[0]

    def _aggregate_subjects(self, results: List[APIResult]) -> tuple:
        """
        Aggregate subjects from multiple results

        Args:
            results: List of API results

        Returns:
            Tuple of (aggregated_subjects, confidence_score)
        """
        subject_scores = Counter()

        for result in results:
            if result.subjects:
                for subject in result.subjects:
                    if subject:
                        key = subject.lower().strip()
                        subject_scores[key] += result.confidence_score

        if not subject_scores:
            return ([], 0.0)

        # Get top subjects
        top_subjects = subject_scores.most_common(10)
        subjects = [s[0].title() for s in top_subjects]

        # Average confidence
        avg_confidence = sum(s[1] for s in top_subjects) / len(top_subjects)

        return (subjects, min(avg_confidence, 1.0))

    def _calculate_overall_confidence(self, metadata: ScoredMetadata,
                                     results: List[APIResult]) -> float:
        """
        Calculate overall confidence score

        Args:
            metadata: Scored metadata
            results: API results

        Returns:
            Overall confidence score (0-1)
        """
        # Weight by field importance
        field_scores = [
            (metadata.title_score, 0.3),
            (metadata.authors_score, 0.25),
            (metadata.isbn_score, 0.2),
            (metadata.publisher_score, 0.1),
            (metadata.published_date_score, 0.1),
            (metadata.description_score, 0.05),
        ]

        weighted_score = sum(score * weight for score, weight in field_scores)

        # Boost if multiple high-confidence sources agree
        if len(results) >= 2:
            high_conf_results = [r for r in results if r.confidence_score >= 0.7]
            if len(high_conf_results) >= 2:
                weighted_score = min(1.0, weighted_score * 1.1)

        return weighted_score

    def _create_fallback_metadata(self, original: EbookMetadata) -> ScoredMetadata:
        """
        Create fallback metadata when no API results available

        Args:
            original: Original metadata

        Returns:
            ScoredMetadata with original values
        """
        metadata = ScoredMetadata(
            title=original.title,
            authors=original.authors,
            isbn=original.isbn,
            isbn13=original.isbn13,
            publisher=original.publisher,
            published_date=original.published_date,
            language=original.language,
            description=original.description,
            subjects=original.subjects,
            overall_confidence=0.0
        )

        return metadata
