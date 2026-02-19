"""
External case law search service.

Searches three authoritative legal databases in parallel:

  1. Slov-lex [SK] – Slovak judicial decisions (HTML search, no public REST API)
     https://www.slov-lex.sk/vyhladavanie?query=...&type=JUDIKATURY

  2. European Commission [EU] – Competition decisions JSON API
     https://competition-cases.ec.europa.eu/api/cases?query=...

  3. CJEU [EU] – Court of Justice via the CELLAR SPARQL endpoint
     https://publications.europa.eu/webapi/rdf/sparql
     This is the official Publications Office semantic repository – the most
     reliable and professional API for EU case law. Returns structured JSON.

All three searches run concurrently via asyncio.gather().
Each source degrades gracefully: on timeout or HTTP error it returns [].
"""
import logging
import re
import asyncio
from typing import List, Dict
from urllib.parse import quote_plus, urlencode

import httpx

logger = logging.getLogger(__name__)

# ── Common HTTP config ────────────────────────────────────────────────────────
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; LegalResearchBot/1.0; "
        "+https://github.com/Rascalcoder/Legislative-AI-Assist)"
    ),
    "Accept-Language": "sk,en;q=0.9,hu;q=0.8",
}
_TIMEOUT = httpx.Timeout(25.0, connect=8.0)

# ── CELLAR / EUR-Lex SPARQL ───────────────────────────────────────────────────
_SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

# CDM namespace – EU Publications Office Common Data Model
_CDM = "http://publications.europa.eu/ontology/cdm#"
_LANG_EN = "http://publications.europa.eu/resource/authority/language/ENG"
_LANG_SK = "http://publications.europa.eu/resource/authority/language/SLK"


# ============================================================
# 1.  Slov-lex  [SK] – Slovak Judicial Decisions
# ============================================================

async def search_slov_lex(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search Slovak judicial decisions (judikatúra) on Slov-lex.

    Slov-lex has no public REST/JSON API for judicial decisions.
    We use their full-text search page and parse the HTML result.

    Returns list of dicts: {title, case_number, url, summary, jurisdiction, source}
    """
    results: List[Dict] = []
    try:
        params = urlencode({"query": query, "type": "JUDIKATURY"})
        url = f"https://www.slov-lex.sk/vyhladavanie?{params}"

        async with httpx.AsyncClient(
            headers={**_HEADERS, "Accept": "text/html"},
            timeout=_TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        results = _parse_slov_lex(response.text, max_results)
        logger.info(f"[Slov-lex] {len(results)} results for '{query[:50]}'")

    except httpx.TimeoutException:
        logger.warning(f"[Slov-lex] timeout – query: '{query[:50]}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"[Slov-lex] HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"[Slov-lex] error: {e}")

    return results


def _parse_slov_lex(html: str, max_results: int) -> List[Dict]:
    """
    Parse Slov-lex search results HTML.

    Targets:
    - Result item headings (h3 / h4 with links)
    - Judicature-specific paths (/judikatury/)
    - Case number patterns (e.g. 3Cdo/12/2020, 4Ob/15/2019)
    """
    results: List[Dict] = []

    # Primary: links inside result-item / search-result divs
    # Slov-lex wraps each result in <li class="list-group-item"> or similar
    item_pattern = re.compile(
        r'href="(/(?:judikatury|vyhladavanie)[^"]+)"[^>]*>\s*<[^>]+>\s*([^<]{5,250})',
        re.IGNORECASE | re.DOTALL,
    )
    # Fallback: any slov-lex internal link with readable title
    generic_pattern = re.compile(
        r'href="(/(?:judikatury|pravne-predpisy)[^"]*)"[^>]*>\s*([A-Z\u00C0-\u017E][^<]{8,250})</a>',
        re.IGNORECASE,
    )
    # Court decision case number: 1Cdo/23/2019, 3Ob/45/2021, etc.
    case_num_re = re.compile(r'\b(\d+\s*[A-Za-z]{1,5}/\d+/\d{4})\b')

    seen: set = set()
    for pattern in (item_pattern, generic_pattern):
        for m in pattern.finditer(html):
            if len(results) >= max_results:
                break
            path = m.group(1).strip()
            raw_title = re.sub(r'\s+', ' ', m.group(2)).strip()
            # Remove HTML tags that crept in
            title = re.sub(r'<[^>]+>', '', raw_title).strip()

            if not title or path in seen or len(title) < 5:
                continue
            seen.add(path)

            cn = case_num_re.search(title)
            results.append({
                "title": title,
                "case_number": cn.group(0) if cn else "",
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
# 2.  EC Competition Decisions  [EU]
# ============================================================

async def search_ec_decisions(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search European Commission competition case law.

    Primary:  JSON REST API at competition-cases.ec.europa.eu/api/cases
    Fallback: HTML search page scraping

    Returns list of dicts: {title, case_number, date, summary, url, jurisdiction, source}
    """
    results: List[Dict] = []

    # ── Primary: JSON API ─────────────────────────────────────────────────────
    try:
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
            r = await client.get(api_url)
            r.raise_for_status()
            data = r.json()

        results = _parse_ec_json(data, max_results)
        if results:
            logger.info(f"[EC API] {len(results)} results for '{query[:50]}'")
            return results

    except httpx.TimeoutException:
        logger.warning(f"[EC API] timeout – query: '{query[:50]}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"[EC API] HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"[EC API] error: {e}")

    # ── Fallback: HTML search ─────────────────────────────────────────────────
    try:
        results = await _scrape_ec_html(query, max_results)
        if results:
            logger.info(f"[EC HTML] {len(results)} results (fallback) for '{query[:50]}'")
    except Exception as e:
        logger.warning(f"[EC HTML] fallback error: {e}")

    return results


def _parse_ec_json(data: dict, max_results: int) -> List[Dict]:
    """Parse EC competition cases JSON API response (handles various response shapes)."""
    results: List[Dict] = []

    items = (
        data.get("items")
        or data.get("cases")
        or data.get("results")
        or data.get("data")
        or (data.get("hits", {}) or {}).get("hits", [])  # Elasticsearch format
        or []
    )

    # Elasticsearch _source unwrap
    unwrapped = [i.get("_source", i) for i in items]

    for item in unwrapped[:max_results]:
        case_num = (
            item.get("caseNumber")
            or item.get("case_number")
            or item.get("reference")
            or ""
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
            or item.get("decisionDate")
            or item.get("date")
            or ""
        ).split("T")[0]  # keep YYYY-MM-DD only

        url = item.get("url") or (
            f"https://competition-cases.ec.europa.eu/cases/{case_num}"
            if case_num else ""
        )

        results.append({
            "title": title,
            "case_number": case_num,
            "date": date,
            "summary": item.get("description") or item.get("summary") or "",
            "url": url,
            "jurisdiction": "EU",
            "source": "EC Competition Decisions",
        })

    return results


async def _scrape_ec_html(query: str, max_results: int) -> List[Dict]:
    """Fallback: parse EC competition search HTML."""
    params = urlencode({"query": query})
    url = f"https://competition-cases.ec.europa.eu/search?{params}"

    async with httpx.AsyncClient(
        headers={**_HEADERS, "Accept": "text/html"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()

    # EC case number formats: AT.40099, M.9000, SA.12345, COMP/M.1234
    cn_re = re.compile(r'\b(AT\.\d+|M\.\d+|SA\.\d+|COMP/[A-Z\d./]+)\b', re.I)
    link_re = re.compile(
        r'href="(/cases/[^"]+)"[^>]*>\s*([^<]{5,200})</a>', re.I
    )

    seen: set = set()
    results: List[Dict] = []
    for m in link_re.finditer(r.text):
        if len(results) >= max_results:
            break
        path, title = m.group(1), m.group(2).strip()
        if path in seen or not title:
            continue
        seen.add(path)
        cn = cn_re.search(title + path)
        results.append({
            "title": title,
            "case_number": cn.group(0) if cn else "",
            "date": "",
            "summary": "",
            "url": f"https://competition-cases.ec.europa.eu{path}",
            "jurisdiction": "EU",
            "source": "EC Competition Decisions",
        })

    return results


# ============================================================
# 3.  CJEU – Court of Justice of the EU  [EU]
#     Via the CELLAR SPARQL endpoint (official Publications Office API)
# ============================================================

def _build_cjeu_sparql(keyword: str, max_results: int) -> str:
    """
    Build a SPARQL query against the CELLAR semantic repository.

    CDM ontology:  http://publications.europa.eu/ontology/cdm#
    Class used:    cdm:judgment   (CJEU / General Court judgments)
    Language:      English expressions (most CJEU judgments have EN titles)

    The query does a case-insensitive CONTAINS filter on the expression title.
    We also try to retrieve the CELEX identifier for constructing the EUR-Lex URL.
    """
    # Escape any quotes in the keyword
    safe_kw = keyword.replace('"', ' ').replace("'", ' ').strip()[:80]

    return f"""
PREFIX cdm:     <{_CDM}>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX lang:    <http://publications.europa.eu/resource/authority/language/>

SELECT DISTINCT ?work ?celex ?date ?title
WHERE {{
  ?work a cdm:judgment ;
        cdm:resource_legal_id_celex ?celex ;
        cdm:work_date_document      ?date ;
        cdm:work_has_expression     ?expr .

  ?expr cdm:expression_uses_language lang:ENG ;
        cdm:expression_title         ?title .

  FILTER ( CONTAINS( LCASE(STR(?title)), LCASE("{safe_kw}") ) )
}}
ORDER BY DESC(?date)
LIMIT {max_results}
"""


async def search_cjeu(query: str, max_results: int = 5) -> List[Dict]:
    """
    Search CJEU case law via the CELLAR SPARQL endpoint.

    This is the official Publications Office machine-readable API.
    Returns application/sparql-results+json – fully structured, no scraping.

    On failure falls back to EUR-Lex full-text search HTML parse.
    """
    results: List[Dict] = []

    # ── Primary: SPARQL ───────────────────────────────────────────────────────
    # Use the first ~3 meaningful words as the keyword to avoid SPARQL injection
    keyword = " ".join(query.split()[:4])

    try:
        sparql_body = _build_cjeu_sparql(keyword, max_results)

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.post(
                _SPARQL_ENDPOINT,
                content=sparql_body.encode(),
                headers={
                    "Content-Type": "application/sparql-query",
                    "Accept": "application/sparql-results+json",
                },
            )
            r.raise_for_status()
            data = r.json()

        results = _parse_sparql_json(data, max_results)
        if results:
            logger.info(
                f"[CJEU SPARQL] {len(results)} results for '{keyword}'"
            )
            return results

        logger.info(f"[CJEU SPARQL] 0 results – trying fallback")

    except httpx.TimeoutException:
        logger.warning(f"[CJEU SPARQL] timeout – keyword: '{keyword}'")
    except httpx.HTTPStatusError as e:
        logger.warning(f"[CJEU SPARQL] HTTP {e.response.status_code}")
    except Exception as e:
        logger.warning(f"[CJEU SPARQL] error: {e}")

    # ── Fallback: EUR-Lex full-text search HTML ───────────────────────────────
    try:
        results = await _scrape_eurlex_html(query, max_results)
        if results:
            logger.info(
                f"[CJEU EUR-Lex HTML] {len(results)} results (fallback)"
            )
    except Exception as e:
        logger.warning(f"[CJEU EUR-Lex HTML] fallback error: {e}")

    return results


def _parse_sparql_json(data: dict, max_results: int) -> List[Dict]:
    """
    Parse application/sparql-results+json response from CELLAR.

    Binding variables: ?work, ?celex, ?date, ?title
    """
    results: List[Dict] = []
    bindings = data.get("results", {}).get("bindings", [])

    for b in bindings[:max_results]:
        celex = b.get("celex", {}).get("value", "")
        title = b.get("title", {}).get("value", "")
        date  = b.get("date",  {}).get("value", "")[:10]   # YYYY-MM-DD

        # Convert CELEX to friendly case number: 62019CJ0001 → C-1/19
        case_num = _celex_to_friendly(celex)

        eur_lex_url = (
            f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
            if celex else ""
        )

        results.append({
            "title": title,
            "case_number": case_num or celex,
            "date": date,
            "summary": "",
            "url": eur_lex_url,
            "jurisdiction": "EU",
            "source": "CJEU / EUR-Lex (CELLAR)",
        })

    return results


def _celex_to_friendly(celex: str) -> str:
    """
    Convert a CELEX number to a readable CJEU case number.

    Examples:
        62019CJ0001  → C-1/19   (Court of Justice)
        62020TJ0050  → T-50/20  (General Court / Tribunal)
        62018CO0123  → C-123/18 (Order)
    """
    # CELEX pattern for case law: 6 + YYYY + TT + NNNN
    m = re.match(r'^6(\d{4})(CJ|TJ|CO|TA)0*(\d+)$', celex, re.I)
    if not m:
        return ""
    year, court_code, num = m.group(1), m.group(2).upper(), m.group(3)
    prefix = "T" if court_code == "TJ" else "C"
    return f"{prefix}-{num}/{year[2:]}"   # e.g. C-1/19


async def _scrape_eurlex_html(query: str, max_results: int) -> List[Dict]:
    """Fallback: parse EUR-Lex full-text search HTML for CJEU judgments."""
    params = urlencode({
        "type": "quick",
        "lang": "en",
        "query": query,
        "DB_TYPE_OF_ACT": "judgment",   # limit to judgments
        "SUBDOM_INIT": "ALL_ALL",
        "DTS_DOM": "EU",
        "locale": "en",
    })
    url = f"https://eur-lex.europa.eu/search-results.html?{params}"

    async with httpx.AsyncClient(
        headers={**_HEADERS, "Accept": "text/html"},
        timeout=_TIMEOUT,
        follow_redirects=True,
    ) as client:
        r = await client.get(url)
        r.raise_for_status()

    link_re = re.compile(
        r'href="(https://eur-lex\.europa\.eu/legal-content/[^"]+)"[^>]*>'
        r'\s*([^<]{10,400})\s*</a>',
        re.I | re.DOTALL,
    )
    celex_re = re.compile(r'CELEX[:%3A]+(6[A-Z0-9]+)', re.I)
    case_re  = re.compile(r'\b([CT]-\d+/\d{2,4})\b')
    date_re  = re.compile(r'\b(\d{4}-\d{2}-\d{2})\b')

    seen: set = set()
    results: List[Dict] = []

    for m in link_re.finditer(r.text):
        if len(results) >= max_results:
            break
        url_val = m.group(1).strip()
        title   = re.sub(r'\s+', ' ', m.group(2)).strip()
        title   = re.sub(r'<[^>]+>', '', title)

        if url_val in seen or not title or len(title) < 10:
            continue
        seen.add(url_val)

        celex_m = celex_re.search(url_val)
        case_m  = case_re.search(title)
        date_m  = date_re.search(title + url_val)

        results.append({
            "title": title,
            "case_number": (
                case_m.group(0) if case_m
                else _celex_to_friendly(celex_m.group(1)) if celex_m
                else ""
            ),
            "date": date_m.group(0) if date_m else "",
            "summary": "",
            "url": url_val,
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

    Method per source:
      slov_lex     → HTML search (Slov-lex has no public judikatúra REST API)
      ec_decisions → JSON REST API  →  HTML fallback
      cjeu         → SPARQL/CELLAR  →  EUR-Lex HTML fallback

    Args:
        query:           Search string optimised for legal databases
        max_per_source:  Maximum results per source (default 5)
        include_sk:      Include Slov-lex [SK]
        include_ec:      Include EC Competition Decisions [EU]
        include_cjeu:    Include CJEU via SPARQL [EU]

    Returns:
        {
            "slov_lex":     [...],   # [SK]
            "ec_decisions": [...],   # [EU]
            "cjeu":         [...],   # [EU]
        }
    """
    task_map: Dict[str, object] = {}
    if include_sk:
        task_map["slov_lex"] = search_slov_lex(query, max_per_source)
    if include_ec:
        task_map["ec_decisions"] = search_ec_decisions(query, max_per_source)
    if include_cjeu:
        task_map["cjeu"] = search_cjeu(query, max_per_source)

    if not task_map:
        return {}

    keys = list(task_map.keys())
    outcomes = await asyncio.gather(
        *[task_map[k] for k in keys], return_exceptions=True
    )

    result: Dict[str, List[Dict]] = {}
    for key, outcome in zip(keys, outcomes):
        if isinstance(outcome, Exception):
            logger.error(f"[search_all_sources] '{key}' raised: {outcome}")
            result[key] = []
        else:
            result[key] = outcome   # type: ignore[assignment]

    total = sum(len(v) for v in result.values())
    logger.info(
        f"[search_all_sources] Done: {total} total results "
        f"across {len(result)} sources | query='{query[:50]}'"
    )
    return result
