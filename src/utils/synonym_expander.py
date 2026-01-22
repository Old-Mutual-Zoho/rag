"""
Synonym and keyword expansion for query enhancement.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Set

import yaml

logger = logging.getLogger(__name__)


class SynonymExpander:
    """
    Expands queries using synonym/keyword mappings.
    """

    def __init__(self, config_path: Path | None = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "keyword_synonyms.yml"

        self.synonyms: Dict[str, List[str]] = {}
        self.categories: Dict[str, List[str]] = {}
        self.abbreviations: Dict[str, str] = {}

        if config_path.exists():
            self._load_config(config_path)
        else:
            logger.warning("Synonym config not found at %s, using empty mappings", config_path)

    def _load_config(self, config_path: Path) -> None:
        """Load synonym mappings from YAML config."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self.synonyms = data.get("synonyms", {})
        self.categories = data.get("categories", {})
        self.abbreviations = data.get("abbreviations", {})

        logger.info(
            "Loaded %d synonym mappings, %d category mappings, %d abbreviations",
            len(self.synonyms),
            len(self.categories),
            len(self.abbreviations),
        )

    def expand_query(self, query: str) -> str:
        """
        Expand a query by adding synonyms and related terms.

        Args:
            query: Original query string

        Returns:
            Expanded query with synonyms added
        """
        query_lower = query.lower()
        expanded_terms: Set[str] = set(query.split())

        # Check for direct synonym matches
        for keyword, synonyms in self.synonyms.items():
            if keyword.lower() in query_lower:
                expanded_terms.update(synonyms)

        # Check for category matches
        for category, terms in self.categories.items():
            if category.lower() in query_lower:
                expanded_terms.update(terms)

        # Check for abbreviations
        for abbrev, full_term in self.abbreviations.items():
            if abbrev.lower() in query_lower:
                expanded_terms.add(full_term)

        # Return expanded query (original + synonyms)
        expanded = " ".join(sorted(expanded_terms))
        if expanded != query:
            logger.debug("Expanded query '%s' -> '%s'", query, expanded)
        return expanded

    def get_synonyms(self, keyword: str) -> List[str]:
        """Get synonyms for a specific keyword."""
        return self.synonyms.get(keyword.lower(), [])
