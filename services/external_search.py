"""
External case law search service.

Searches three authoritative legal databases in parallel:
  1. Slov-lex (SK) - Slovak judicial decisions database
  2. European Commission - Competition decisions (competition-cases.ec.europa.eu)
  3. CJEU - Court of Justice of the EU (via EUR-Lex / InfoCuria)

Results are returned with jurisdiction labels [SK] or [EU] and source metadata.
"""
import logging
import re
import asyncio
from typing import List, Dict
from urllib.parse import quote_plus, urlencode

import httpx

logger = logging.getLogger(__name__)

# HTTP client defaults
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LegalResearchBot/1.0; "
        "Educational/Professional Legal Research)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "application/json,*/*;q=0.8"
    ),
    "Accept-Language": "sk,en;q=0.9,hu;q=0.8",
}
_TIMEOUT = httpx.Timeout(20.0, connect=8.0)


# ============================================================
# 1. Slov-lex (SK Judicial Decisions)
# ============================================================

async def search_slov_lex(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search Slovak judicial decisions (judikatúra) on Slov-lex.

    Targets the full-text search at www.slov-lex.sk.
    Returns list of dicts: {title, case_number, url, summary, jurisdiction, source}
    """
    results = []
    try:
        # Slov-lex full-text search with judicature filter
        params = urlencode({
            "query": query,
            "type": "JUDIKATURY",
        })
        url = f"https://www.slov-lex.sk/vyhladavanie?{params}"

        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            results = _parse_slov_lex_html(response.text, max_results)
            logger.info(
                f"Slov-lex: {len(results)} results for '{query[:50]}'"
            )

    except httpx.TimeoutException:
        logger.warning(f"Slov-lex: timeout for query '{query[:50]}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"Slov-lex: HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"Slov-lex: search error - {e}")

    return results


def _parse_slov_lex_html(html: str, max_results: int) -> List[Dict]:
    """Parse Slov-lex HTML search results to extract case references."""
    results = []

    # Primary pattern: links to judicature/legislation entries
    link_pattern = re.compile(
        r'href="(/(?:judikatury|pravne-predpisy)[^"]*)"[^>]*>\s*([^<]{8,300})\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )

    # Secondary: generic slov-lex document links
    fallback_pattern = re.compile(
        r'href="(/[^"]{5,})"[^>]*class="[^"]*(?:result|title|link)[^"]*"[^>]*>\s*([^<]{8,300})</a>',
        re.IGNORECASE,
    )

    # Pattern to detect court decision case numbers (e.g. "1Cdo/12/2019")
    case_num_pattern = re.compile(
        r'\b(\d+[A-Za-z]+/\d+/\d{4}|\d{4}/\d+)\b'
    )

    seen = set()
    for pattern in (link_pattern, fallback_pattern):
        for match in pattern.finditer(html):
            if len(results) >= max_results:
                break
            path = match.group(1).strip()
            title = re.sub(r'\s+', ' ', match.group(2)).strip()

            if not title or path in seen or len(title) < 8:
                continue

            seen.add(path)
            case_num_match = case_num_pattern.search(title)

            results.append({
                "title": title,
                "case_number": case_num_match.group(0) if case_num_match else "",
                "date": "",
                "summary": "",
                "url": f"https://www.slov-lex.sk{path}",
                "jurisdiction": "SK",
                "source": "Slov-lex",
            })

        if len(results) >= max_results:
            break

    return results


# ============================================================
# 2. European Commission Competition Decisions
# ============================================================

async def search_ec_decisions(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search European Commission competition case law.

    Uses the public competition-cases.ec.europa.eu API.
    Returns list of dicts: {title, case_number, date, summary, url, jurisdiction, source}
    """
    results = []
    try:
        # Try the EC competition cases API (JSON)
        params = urlencode({
            "query": query,
            "size": max_results,
            "language": "EN",
            "sort": "relevance",
        })
        api_url = f"https://competition-cases.ec.europa.eu/api/cases?{params}"

        async with httpx.AsyncClient(
            headers={**_HEADERS, "Accept": "application/json"},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            data = response.json()
            results = _parse_ec_json(data, max_results)

        if not results:
            # Fallback: scrape the search page
            results = await _scrape_ec_search(query, max_results)

        logger.info(f"EC Decisions: {len(results)} results for '{query[:50]}'")

    except httpx.TimeoutException:
        logger.warning(f"EC Decisions: timeout for query '{query[:50]}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"EC Decisions: HTTP {e.response.status_code}")
        # Fallback to HTML scraping
        try:
            results = await _scrape_ec_search(query, max_results)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"EC Decisions: error - {e}")

    return results


def _parse_ec_json(data: dict, max_results: int) -> List[Dict]:
    """Parse EC competition cases JSON API response."""
    results = []

    # Handle various possible response shapes
    items = (
        data.get("items")
        or data.get("cases")
        or data.get("results")
        or data.get("data")
        or []
    )

    for item in items[:max_results]:
        case_num = (
            item.get("caseNumber")
            or item.get("case_number")
            or item.get("reference", "")
        )
        title = (
            item.get("caseName")
            or item.get("title")
            or item.get("name")
            or case_num
            or ""
        )
        date = str(
            item.get("closingDate")
            or item.get("date")
            or item.get("decisionDate", "")
        )
        url = item.get("url", "")
        if not url and case_num:
            url = f"https://competition-cases.ec.europa.eu/cases/{case_num}"

        results.append({
            "title": title,
            "case_number": case_num,
            "date": date,
            "summary": item.get("description") or item.get("summary", ""),
            "url": url,
            "jurisdiction": "EU",
            "source": "EC Competition Decisions",
        })

    return results


async def _scrape_ec_search(query: str, max_results: int) -> List[Dict]:
    """Fallback: scrape EC competition decisions search page."""
    results = []
    params = urlencode({"query": query})
    url = f"https://competition-cases.ec.europa.eu/search?{params}"

    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    # Extract case references from HTML
    # Pattern: AT.XXXXX or M.XXXX or SA.XXXX (EC case number formats)
    case_ref_pattern = re.compile(
        r'(AT\.\d+|M\.\d+|SA\.\d+|COMP/[A-Z\d./]+)',
        re.IGNORECASE,
    )
    link_pattern = re.compile(
        r'href="(/cases/[^"]+)"[^>]*>\s*([^<]{5,200})</a>',
        re.IGNORECASE,
    )

    seen = set()
    for match in link_pattern.finditer(response.text):
        if len(results) >= max_results:
            break
        path = match.group(1)
        title = match.group(2).strip()
        if path in seen or not title:
            continue
        seen.add(path)

        case_match = case_ref_pattern.search(title + path)
        results.append({
            "title": title,
            "case_number": case_match.group(0) if case_match else "",
            "date": "",
            "summary": "",
            "url": f"https://competition-cases.ec.europa.eu{path}",
            "jurisdiction": "EU",
            "source": "EC Competition Decisions",
        })

    return results


# ============================================================
# 3. CJEU - Court of Justice of the EU (via EUR-Lex)
# ============================================================

async def search_cjeu(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search CJEU case law via EUR-Lex full-text search.

    Targets CJEU judgments and opinions (CELEX domain 6).
    Returns list of dicts: {title, case_number, date, url, jurisdiction, source}
    """
    results = []
    try:
        # EUR-Lex case law search - filter to CJEU domain
        params = urlencode({
            "type": "quick",
            "lang": "en",
            "query": query,
            "SUBDOM_INIT": "ALL_ALL",
            "DTS_DOM": "EU",
            "DTA_TYPE": "ALL",
            "locale": "en",
        })
        url = f"https://eur-lex.europa.eu/search-results.html?{params}"

        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            results = _parse_eurlex_html(response.text, max_results)

        logger.info(f"CJEU/EUR-Lex: {len(results)} results for '{query[:50]}'")

    except httpx.TimeoutException:
        logger.warning(f"CJEU: timeout for query '{query[:50]}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"CJEU: HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"CJEU: search error - {e}")

    return results


def _parse_eurlex_html(html: str, max_results: int) -> List[Dict]:
    """
    Parse EUR-Lex search results HTML.

    Extracts document links - prioritises CJEU case law (CELEX 6xxxxxx).
    """
    results = []

    # Pattern: EUR-Lex legal-content document links
    link_pattern = re.compile(
        r'href="(https://eur-lex\.europa\.eu/legal-content/[^"]+)"[^>]*>'
        r'\s*([^<]{10,400})\s*</a>',
        re.IGNORECASE | re.DOTALL,
    )

    # CELEX pattern: case law starts with 6
    celex_pattern = re.compile(r'CELEX%3A(6[A-Z0-9]+)|CELEX:(6[A-Z0-9]+)', re.IGNORECASE)

    # Case number pattern: C-123/45 or T-456/78
    cjeu_case_pattern = re.compile(r'\b([CT]-\d+/\d{2,4}(?:P?(?:\s+\w+)?))\b')

    # Date pattern: YYYY-MM-DD or DD/MM/YYYY
    date_pattern = re.compile(r'\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})\b')

    seen_urls = set()
    for match in link_pattern.finditer(html):
        if len(results) >= max_results:
            break

        url = match.group(1).strip()
        title = re.sub(r'\s+', ' ', match.group(2)).strip()

        if url in seen_urls or not title or len(title) < 10:
            continue

        # Skip non-case-law links (legislation, summaries, etc.) if possible
        # by preferring CELEX numbers that start with 6
        celex_match = celex_pattern.search(url)
        celex = (celex_match.group(1) or celex_match.group(2)) if celex_match else ""

        cjeu_match = cjeu_case_pattern.search(title)
        case_num = cjeu_match.group(0) if cjeu_match else celex

        date_match = date_pattern.search(title + url)
        date = date_match.group(0) if date_match else ""

        seen_urls.add(url)
        results.append({
            "title": title,
            "case_number": case_num,
            "date": date,
            "summary": "",
            "url": url,
            "jurisdiction": "EU",
            "source": "CJEU / EUR-Lex",
        })

    return results


# ============================================================
# Parallel orchestration
# ============================================================

async def search_all_sources(
    query: str,
    max_per_source: int = 5,
    include_sk: bool = True,
    include_ec: bool = True,
    include_cjeu: bool = True,
) -> Dict[str, List[Dict]]:
    """
    Search all external case law sources in parallel.

    Args:
        query:           Search string (optimised for legal databases)
        max_per_source:  Maximum results per source database
        include_sk:      Include Slov-lex (Slovak decisions)
        include_ec:      Include EC competition decisions
        include_cjeu:    Include CJEU case law via EUR-Lex

    Returns:
        {
            "slov_lex":     [...],   # [SK] results
            "ec_decisions": [...],   # [EU] results
            "cjeu":         [...],   # [EU] results
        }
    """
    task_map = {}

    if include_sk:
        task_map["slov_lex"] = search_slov_lex(query, max_per_source)
    if include_ec:
        task_map["ec_decisions"] = search_ec_decisions(query, max_per_source)
    if include_cjeu:
        task_map["cjeu"] = search_cjeu(query, max_per_source)

    if not task_map:
        return {}

    keys = list(task_map.keys())
    coros = [task_map[k] for k in keys]

    task_results = await asyncio.gather(*coros, return_exceptions=True)

    results: Dict[str, List[Dict]] = {}
    for key, outcome in zip(keys, task_results):
        if isinstance(outcome, Exception):
            logger.error(f"External search '{key}' raised: {outcome}")
            results[key] = []
        else:
            results[key] = outcome

    total = sum(len(v) for v in results.values())
    logger.info(
        f"External search complete: {total} results "
        f"across {len(results)} sources for '{query[:50]}'"
    )
    return results
