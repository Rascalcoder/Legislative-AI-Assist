"""
Case Retrieval Service - Integrates external case sources with main search.

Fetches real court cases and decisions from external sources and combines
them with Supabase hybrid search results.

Sources:
- SK: NSSUD (Najvyšší správny súd SR) + PMÚ (Protimonopolný úrad SR)
- EU: EUR-Lex (CJEU judgments) + EU Commission competition decisions
"""
import asyncio
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

from services.nssud_scraper import scrape_nssud_cases
from services.eurlex_service import EurLexService
from services.pmu_service import PMUService

logger = logging.getLogger(__name__)


class CaseRetrievalService:
    """Service for retrieving court cases from external sources."""

    def __init__(self):
        self.eurlex = EurLexService()
        self.pmu = PMUService()
        self.cache: dict = {}
        self.cache_ttl = 3600  # 1 hour

    async def search_cases(
        self,
        query: str,
        jurisdiction: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search for relevant court cases across all enabled sources in parallel.

        Args:
            query: User query
            jurisdiction: 'SK' or 'EU' or None (both)
            date_from: Start date (dd.mm.yyyy or ISO)
            date_to: End date (dd.mm.yyyy or ISO)
            limit: Max results per jurisdiction (total may be 2x limit when both)

        Returns:
            List of case dictionaries with URLs and metadata
        """
        tasks = []

        if jurisdiction in ("SK", None):
            tasks.append(self._search_sk_cases(query, date_from, date_to, limit))
        if jurisdiction in ("EU", None):
            tasks.append(self._search_eu_cases(query, date_from, date_to, limit))

        if not tasks:
            return []

        # Run all jurisdiction searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_cases: List[Dict] = []
        for r in results:
            if isinstance(r, list):
                all_cases.extend(r)
            elif isinstance(r, Exception):
                logger.error(f"Case search task failed: {r}")

        # Rank and return (up to 2x limit to give room for both jurisdictions)
        ranked = self._rank_cases(all_cases, query)
        return ranked[:limit * 2]

    async def _search_sk_cases(
        self,
        query: str,
        date_from: Optional[str],
        date_to: Optional[str],
        limit: int,
    ) -> List[Dict]:
        """Search Slovak court cases: NSSUD + PMÚ in parallel."""
        cache_key = f"SK_{query}_{date_from}_{date_to}_{limit}"
        if cache_key in self.cache:
            cached_at, cached_data = self.cache[cache_key]
            if datetime.utcnow().timestamp() - cached_at < self.cache_ttl:
                logger.info("Returning cached SK cases")
                return cached_data

        per_source = max(limit // 2, 10)

        nssud_task = scrape_nssud_cases(date_from, date_to, per_source)
        pmu_task = self.pmu.search_decisions(query, per_source)

        nssud_result, pmu_result = await asyncio.gather(
            nssud_task, pmu_task, return_exceptions=True
        )

        cases: List[Dict] = []
        if isinstance(nssud_result, list):
            cases.extend(nssud_result)
        else:
            logger.error(f"NSSUD search failed: {nssud_result}")

        if isinstance(pmu_result, list):
            cases.extend(pmu_result)
        else:
            logger.error(f"PMÚ search failed: {pmu_result}")

        self.cache[cache_key] = (datetime.utcnow().timestamp(), cases)
        return cases

    async def _search_eu_cases(
        self,
        query: str,
        date_from: Optional[str],  # noqa: ARG002 — reserved for future date filtering
        date_to: Optional[str],    # noqa: ARG002 — reserved for future date filtering
        limit: int,
    ) -> List[Dict]:
        """Search EU court cases: EUR-Lex CJEU + EC Commission decisions."""
        cache_key = f"EU_{query}_{limit}"
        if cache_key in self.cache:
            cached_at, cached_data = self.cache[cache_key]
            if datetime.utcnow().timestamp() - cached_at < self.cache_ttl:
                logger.info("Returning cached EU cases")
                return cached_data

        cases = await self.eurlex.search_competition_cases(query, limit)
        self.cache[cache_key] = (datetime.utcnow().timestamp(), cases)
        return cases

    def _rank_cases(self, cases: List[Dict], query: str) -> List[Dict]:
        """
        Rank cases by relevance to query using keyword matching.

        Title matches are weighted 3x vs content matches.
        """
        query_lower = query.lower()
        query_words = set(re.split(r"\W+", query_lower)) - {"", "a", "the", "of", "in", "to"}

        for case in cases:
            title = (case.get("title") or "").lower()
            topic = (case.get("topic") or "").lower()
            case_number = (case.get("case_number") or "").lower()

            title_words = set(re.split(r"\W+", title))
            topic_words = set(re.split(r"\W+", topic))

            title_matches = len(query_words & title_words)
            topic_matches = len(query_words & topic_words)
            # Bonus for query terms appearing in case number (e.g. "AT.40099")
            cn_bonus = 1 if any(w in case_number for w in query_words if len(w) > 3) else 0

            case["relevance_score"] = (title_matches * 3) + topic_matches + cn_bonus

        return sorted(cases, key=lambda x: x.get("relevance_score", 0), reverse=True)

    def clear_cache(self):
        """Clear all cached results."""
        self.cache = {}


# Global singleton
_case_service: Optional[CaseRetrievalService] = None


def get_case_service() -> CaseRetrievalService:
    """Get or create the case retrieval service singleton."""
    global _case_service
    if _case_service is None:
        _case_service = CaseRetrievalService()
    return _case_service
