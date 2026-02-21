"""
PMÚ (Protimonopolný úrad Slovenskej republiky) Decisions Scraper

Sources tried in order:
1. /prehlad-rozodnuti/ — static decision list (may be JS-rendered)
2. /aktuality/ — news articles about decisions
3. Category pages: /kartely/, /zneuzivanie-dominantneho-postavenia/, /koncentracie/

Note: PMÚ's website uses a modern CMS that partially renders via JavaScript,
so scraped results may be limited. Graceful fallback returns empty list.
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
    "Accept-Language": "sk,en;q=0.9",
}

_BASE_URL = "https://www.antimon.gov.sk"

# Category pages that list competition law content
_CATEGORY_PAGES = [
    "/kartely/",
    "/zneuzivanie-dominantneho-postavenia/",
    "/koncentracie/",
    "/vertikalne-dohody/",
]


class PMUService:
    """
    Scraper for PMÚ (Protimonopolný úrad SR) competition decisions.
    Covers: cartel decisions, abuse of dominance, merger control.
    """

    async def search_decisions(self, query: str, limit: int = 50) -> List[Dict]:
        """
        Fetch PMÚ decisions and news articles about competition law cases.

        Args:
            query: Search query (used for relevance filtering)
            limit: Maximum number of results

        Returns:
            List of decision dicts with URLs and metadata
        """
        _ = query  # used in relevance ranking by case_retrieval._rank_cases()
        all_decisions: List[Dict] = []

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers=_HEADERS,
        ) as client:
            # 1. Try category pages (static HTML, most reliable)
            for path in _CATEGORY_PAGES:
                if len(all_decisions) >= limit:
                    break
                try:
                    resp = await client.get(f"{_BASE_URL}{path}")
                    if resp.status_code == 200:
                        items = self._parse_page(resp.text, path)
                        all_decisions.extend(items)
                except Exception as e:
                    logger.debug(f"PMÚ page {path} failed: {e}")

            # 2. Try aktuality (news about recent decisions)
            if len(all_decisions) < limit:
                try:
                    resp = await client.get(f"{_BASE_URL}/aktuality/")
                    if resp.status_code == 200:
                        items = self._parse_aktuality(resp.text)
                        all_decisions.extend(items)
                except Exception as e:
                    logger.debug(f"PMÚ aktuality failed: {e}")

        # Deduplicate by URL
        seen: set = set()
        unique: List[Dict] = []
        for d in all_decisions:
            if d["url"] not in seen:
                seen.add(d["url"])
                unique.append(d)

        logger.info(f"PMÚ: found {len(unique)} decisions/articles")
        return unique[:limit]

    def _parse_page(self, html: str, source_path: str) -> List[Dict]:
        """Parse a PMÚ category page for decision-related links."""
        soup = BeautifulSoup(html, "html.parser")
        decisions: List[Dict] = []

        # Look for internal links that are not nav/footer links
        main_content = (
            soup.find("main")
            or soup.find("div", id=re.compile(r"content|main", re.I))
            or soup.find("div", class_=re.compile(r"content|main|article", re.I))
            or soup
        )

        for link in main_content.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            # Skip nav/social/empty links
            if not text or len(text) < 8:
                continue
            if re.match(r"^(javascript|mailto|#|https?://(www\.)?(facebook|twitter|instagram|linkedin))", href, re.I):
                continue

            # Build absolute URL
            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = f"{_BASE_URL}{href}"
            else:
                continue

            # Only include antimon.gov.sk links
            if "antimon.gov.sk" not in url:
                continue

            # Skip pure navigation pages
            if re.search(r"/(en|sk)/?$|/kontakt|/o-urade|/financie|/kariera|/kniznica|/podatelna|instagram|facebook|twitter|linkedin", url, re.I):
                continue

            case_number = self._extract_case_number(text) or self._extract_case_number(href)
            date = self._extract_date(text)

            # Categorize by source path
            topic = self._path_to_topic(source_path)

            decisions.append({
                "source": "PMÚ",
                "case_number": case_number or text[:60],
                "url": url,
                "title": text[:200],
                "court": "Protimonopolný úrad SR",
                "date": date,
                "jurisdiction": "SK",
                "type": "authority_decision",
                "topic": topic,
                "scraped_at": datetime.utcnow().isoformat(),
            })

        return decisions

    def _parse_aktuality(self, html: str) -> List[Dict]:
        """Parse PMÚ news page for decision announcements."""
        soup = BeautifulSoup(html, "html.parser")
        decisions: List[Dict] = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            # Only long descriptive links (news articles)
            if len(text) < 20:
                continue
            if not re.search(r"kartel|pokuta|rozhodnut|zneuz|dominantn|koncentr|sutaz|súťaž", text, re.I):
                continue

            if href.startswith("http"):
                url = href
            elif href.startswith("/"):
                url = f"{_BASE_URL}{href}"
            else:
                continue

            if "antimon.gov.sk" not in url:
                continue

            decisions.append({
                "source": "PMÚ",
                "case_number": self._extract_case_number(text) or text[:60],
                "url": url,
                "title": text[:200],
                "court": "Protimonopolný úrad SR",
                "date": self._extract_date(text),
                "jurisdiction": "SK",
                "type": "authority_decision",
                "topic": "hospodárska súťaž",
                "scraped_at": datetime.utcnow().isoformat(),
            })

        return decisions

    def _path_to_topic(self, path: str) -> str:
        mapping = {
            "/kartely/": "kartelové dohody",
            "/zneuzivanie-dominantneho-postavenia/": "zneužívanie dominantného postavenia",
            "/koncentracie/": "kontrola koncentrácií",
            "/vertikalne-dohody/": "vertikálne dohody",
        }
        return mapping.get(path, "hospodárska súťaž")

    def _extract_case_number(self, text: str) -> Optional[str]:
        """Extract PMÚ case reference (e.g. 2023/DZ/1/1, POK-001/2023)."""
        patterns = [
            r"\d{4}/[A-Z]+/\d+/\d+",
            r"[A-Z]+-\d{3,}/\d{4}",
            r"[A-Z]{2,3}-\d+/\d{4}",
            r"\d{4}/[A-Z]+/\d+",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """Parse date from text (dd.mm.yyyy or year only)."""
        match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        match = re.search(r"\b(20\d{2})\b", text)
        return match.group(1) if match else None
