"""
NSSUD (Najvyšší správny súd SR) Case Scraper
Fetches competition law cases from Slovak Supreme Administrative Court via RSS feed.

URL: https://www.nssud.sk/
Focus: "hospodárska súťaž" (competition law) cases

Note: NSSUD does not expose a public search API. We use their WordPress RSS feed
(100 most recent articles) and filter for competition law relevance.
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
    "Accept": "application/rss+xml, text/xml, */*",
    "Accept-Language": "sk,en;q=0.9",
}

# Competition law keywords for relevance filtering
_COMPETITION_KEYWORDS = [
    "hospodárska súťaž", "sutaz", "kartel", "kartelová", "monopol",
    "dominantn", "antimonopol", "pmu", "protimonopoln",
    "koncentrác", "fúzi", "zneužív", "hospodárenie",
    "competition", "antitrust", "cartel",
]


class NSSUDScraper:
    """Scraper for NSSUD competition law cases via RSS feed."""

    BASE_URL = "https://www.nssud.sk"
    RSS_URL = f"{BASE_URL}/feed/"

    async def search_competition_cases(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Fetch recent NSSUD articles/decisions and filter for competition law relevance.

        Args:
            date_from: Date from (dd.mm.yyyy) — not used for RSS filtering (RSS returns latest)
            date_to: Date to (dd.mm.yyyy) — not used for RSS filtering
            limit: Maximum number of results

        Returns:
            List of case dictionaries with metadata and URLs
        """
        try:
            _ = date_from, date_to  # RSS returns latest items; date params kept for API compatibility
            logger.info("Fetching NSSUD RSS feed for competition law cases")

            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers=_HEADERS,
            ) as client:
                response = await client.get(self.RSS_URL)
                response.raise_for_status()

            cases = self._parse_rss_feed(response.text, limit)
            logger.info(f"Found {len(cases)} competition-related items from NSSUD RSS")
            return cases

        except Exception as e:
            logger.error(f"Error fetching NSSUD RSS feed: {e}")
            return []

    def _parse_rss_feed(self, xml: str, limit: int) -> List[Dict]:
        """Parse WordPress RSS feed and filter for competition law relevance."""
        soup = BeautifulSoup(xml, "xml")
        cases: List[Dict] = []

        for item in soup.find_all("item"):
            if len(cases) >= limit:
                break

            title_elem = item.find("title")
            link_elem = item.find("link")
            desc_elem = item.find("description")
            pub_date_elem = item.find("pubDate")

            title = title_elem.get_text(strip=True) if title_elem else ""
            url = link_elem.get_text(strip=True) if link_elem else ""
            description = desc_elem.get_text(strip=True) if desc_elem else ""
            pub_date = pub_date_elem.get_text(strip=True) if pub_date_elem else ""

            # Filter for competition law relevance
            combined_text = (title + " " + description).lower()
            if not any(kw in combined_text for kw in _COMPETITION_KEYWORDS):
                continue

            if not url:
                continue

            date_iso = self._parse_rss_date(pub_date) if pub_date else None

            # Generate case number from URL slug
            slug = url.rstrip("/").split("/")[-1]
            case_number = slug[:60] if slug else "NSSUD-article"

            cases.append({
                "source": "NSSUD",
                "case_number": case_number,
                "url": url,
                "title": title[:200] or "NSSUD – Competition Law",
                "date": date_iso,
                "court": "Najvyšší správny súd SR",
                "jurisdiction": "SK",
                "type": "court_decision",
                "topic": "hospodárska súťaž",
                "scraped_at": datetime.utcnow().isoformat(),
            })

        return cases

    def _parse_rss_date(self, date_str: str) -> Optional[str]:
        """Parse RSS pubDate (RFC 2822) to ISO date string."""
        try:
            # RSS dates: "Fri, 21 Feb 2026 12:00:00 +0000"
            match = re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", date_str)
            if match:
                day, month_abbr, year = match.groups()
                months = {
                    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
                    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
                    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
                }
                month = months.get(month_abbr, "01")
                return f"{year}-{month}-{day.zfill(2)}"
        except Exception:
            pass
        return None

    async def get_case_details(self, url: str) -> Optional[Dict]:
        """Fetch full case details from NSSUD article URL."""
        try:
            async with httpx.AsyncClient(
                timeout=20.0,
                follow_redirects=True,
                headers={**_HEADERS, "Accept": "text/html,*/*"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            content = soup.find(["article", "div"], class_=re.compile(r"content|entry|post", re.I))
            return {
                "url": url,
                "full_text": content.get_text(strip=True)[:3000] if content else None,
                "summary": None,
            }
        except Exception as e:
            logger.error(f"Error fetching NSSUD article {url}: {e}")
            return None


async def scrape_nssud_cases(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> List[Dict]:
    """
    Convenience function to fetch NSSUD competition law cases via RSS.

    Args:
        date_from: Start date (informational, not used for RSS filtering)
        date_to: End date (informational, not used for RSS filtering)
        limit: Max results

    Returns:
        List of competition-law-related case dictionaries
    """
    scraper = NSSUDScraper()
    return await scraper.search_competition_cases(date_from, date_to, limit)
