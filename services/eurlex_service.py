"""
EUR-Lex & EU Commission Competition Cases Service

Sources:
- EUR-Lex case law search (CJEU judgments): https://eur-lex.europa.eu/search.html
- EU Commission competition cases portal: https://competition-cases.ec.europa.eu/

Returns real case URLs and metadata for competition law cases.
"""
import logging
import re
from typing import List, Dict, Optional
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,sk;q=0.9",
}


class EurLexService:
    """
    Searches EUR-Lex for CJEU competition law judgments and
    EU Commission competition decisions.
    """

    EURLEX_BASE = "https://eur-lex.europa.eu"
    EURLEX_SEARCH = f"{EURLEX_BASE}/search.html"
    EC_COMPETITION = "https://competition-cases.ec.europa.eu/search"

    async def search_competition_cases(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Search for EU competition law cases from:
        1. EUR-Lex CJEU case law (judgments on Art. 101/102 TFEU, mergers)
        2. EU Commission competition decisions portal

        Args:
            query: Search query (keywords, case name, article reference)
            limit: Maximum total results

        Returns:
            List of case dicts with URLs, case numbers, courts, dates
        """
        per_source = max(limit // 2, 10)
        results: List[Dict] = []

        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            # 1. CJEU judgments via EUR-Lex
            try:
                cjeu_cases = await self._search_eurlex_caselaw(client, query, per_source)
                results.extend(cjeu_cases)
                logger.info(f"EUR-Lex CJEU: found {len(cjeu_cases)} cases for '{query[:60]}'")
            except Exception as e:
                logger.error(f"EUR-Lex CJEU search error: {e}")

            # 2. EU Commission competition decisions
            try:
                ec_cases = await self._search_ec_decisions(client, query, per_source)
                results.extend(ec_cases)
                logger.info(f"EC Competition: found {len(ec_cases)} cases for '{query[:60]}'")
            except Exception as e:
                logger.error(f"EC Competition search error: {e}")

        return results[:limit]

    async def _search_eurlex_caselaw(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> List[Dict]:
        """Search CJEU judgments via EUR-Lex.

        Note: DTS_SUBDOM=CASE_LAW causes HTTP 500 on EUR-Lex servers.
        Instead we add 'judgment' to the query to surface case law results,
        then filter by CELEX numbers starting with '6' (case law prefix).
        """
        # Prepend 'judgment' to bias results towards CJEU/General Court decisions
        search_text = f"judgment {query}" if "judgment" not in query.lower() else query
        params = {
            "scope": "EURLEX",
            "type": "quick",
            "lang": "en",
            "text": search_text,
        }
        resp = await client.get(self.EURLEX_SEARCH, params=params)
        resp.raise_for_status()
        return self._parse_eurlex_results(resp.text, limit)

    def _parse_eurlex_results(self, html: str, limit: int) -> List[Dict]:
        """Parse EUR-Lex search result HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cases: List[Dict] = []

        # EUR-Lex result links contain ?uri=CELEX:... or legal-content paths
        # Deduplicate by CELEX number: each case appears 3x (AUTO/PDF/HTML links)
        # Keep only the AUTO link (human-readable viewer)
        seen_celex: set = set()
        for link in soup.find_all("a", href=re.compile(r"CELEX|legal-content")):
            if len(cases) >= limit:
                break

            href = link.get("href", "")
            if not href:
                continue

            celex = self._extract_celex(href)

            # Only include case law (CELEX numbers starting with 6 = case law)
            if not celex or not celex.startswith("6"):
                continue

            # Skip PDF/HTML variants — keep only the AUTO (main viewer) link
            if "/TXT/PDF/" in href or "/TXT/HTML/" in href:
                continue

            if celex in seen_celex:
                continue
            seen_celex.add(celex)

            # Build absolute URL (EUR-Lex returns relative ./legal-content/... paths)
            if href.startswith("./"):
                url = f"{self.EURLEX_BASE}{href[1:]}"
            elif href.startswith("/"):
                url = f"{self.EURLEX_BASE}{href}"
            elif href.startswith("http"):
                url = href
            else:
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                # Generate title from CELEX number if link text is empty
                title = f"CJEU Case {celex}"

            cases.append({
                "source": "EUR-Lex",
                "case_number": celex,
                "url": url,
                "title": title[:200],
                "court": "Court of Justice of the EU / General Court",
                "jurisdiction": "EU",
                "type": "court_decision",
                "topic": "competition law",
                "scraped_at": datetime.utcnow().isoformat(),
            })

        return cases

    async def _search_ec_decisions(
        self, client: httpx.AsyncClient, query: str, limit: int
    ) -> List[Dict]:
        """Search EU Commission competition decisions portal."""
        cases: List[Dict] = []

        # Try JSON API first
        try:
            resp = await client.get(
                self.EC_COMPETITION,
                params={"search": query, "page": 1, "pageSize": min(limit, 25)},
                headers={**_HEADERS, "Accept": "application/json"},
                timeout=20.0,
            )
            if resp.status_code == 200 and "application/json" in resp.headers.get("content-type", ""):
                data = resp.json()
                cases = self._parse_ec_json(data, limit)
                if cases:
                    return cases
        except Exception:
            pass

        # Fallback: scrape HTML
        try:
            resp = await client.get(
                "https://competition-cases.ec.europa.eu/cases",
                params={"search": query},
                headers=_HEADERS,
                timeout=20.0,
            )
            if resp.status_code == 200:
                cases = self._parse_ec_html(resp.text, limit)
        except Exception as e:
            logger.debug(f"EC HTML fallback failed: {e}")

        return cases

    def _parse_ec_json(self, data: dict, limit: int) -> List[Dict]:
        """Parse EU Commission competition cases JSON response."""
        cases: List[Dict] = []
        items = data.get("cases") or data.get("results") or data.get("items") or []
        for item in items[:limit]:
            case_number = item.get("caseNumber") or item.get("case_number") or item.get("id", "")
            title = item.get("caseName") or item.get("name") or item.get("title", "")
            url = (
                item.get("url")
                or f"https://competition-cases.ec.europa.eu/cases/{case_number}"
                if case_number else ""
            )
            date = item.get("decisionDate") or item.get("date") or item.get("year", "")
            cases.append({
                "source": "EU Commission",
                "case_number": str(case_number),
                "url": url,
                "title": str(title)[:200],
                "court": "European Commission DG COMP",
                "date": str(date) if date else None,
                "jurisdiction": "EU",
                "type": "authority_decision",
                "topic": "competition law",
                "scraped_at": datetime.utcnow().isoformat(),
            })
        return cases

    def _parse_ec_html(self, html: str, limit: int) -> List[Dict]:
        """Parse EU Commission competition cases HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cases: List[Dict] = []
        seen = set()

        for link in soup.find_all("a", href=re.compile(r"/cases/", re.I)):
            if len(cases) >= limit:
                break
            href = link.get("href", "")
            url = href if href.startswith("http") else f"https://competition-cases.ec.europa.eu{href}"
            if url in seen:
                continue
            seen.add(url)
            title = link.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            # Extract case number from URL or text (e.g. AT.40099, M.8084)
            case_number = self._extract_ec_case_number(href) or self._extract_ec_case_number(title) or title[:50]
            cases.append({
                "source": "EU Commission",
                "case_number": case_number,
                "url": url,
                "title": title[:200],
                "court": "European Commission DG COMP",
                "jurisdiction": "EU",
                "type": "authority_decision",
                "topic": "competition law",
                "scraped_at": datetime.utcnow().isoformat(),
            })
        return cases

    def _extract_celex(self, text: str) -> Optional[str]:
        """Extract CELEX number from URL or text (e.g. 62019CJ0001)."""
        match = re.search(r"CELEX[:%]([A-Z0-9]+)", text, re.I)
        if match:
            return match.group(1)
        # Also handle uri=CELEX:62019CJ0001 format
        match = re.search(r"uri=CELEX:([A-Z0-9]+)", text, re.I)
        if match:
            return match.group(1)
        return None

    def _extract_ec_case_number(self, text: str) -> Optional[str]:
        """Extract EC case number (e.g. AT.40099, M.8084, COMP/M.1234)."""
        match = re.search(r"(?:AT\.\d+|M\.\d+|COMP/[A-Z.]+\d+)", text, re.I)
        return match.group(0) if match else None
