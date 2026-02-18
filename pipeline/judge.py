"""
Judge Pipeline - AI Judge Assistant.

4-step analytical workflow:
  Step 1: define_topic()     - Extract and define the legal topic from the case description
  Step 2: search_case_law()  - Search external databases in parallel:
                                 · Slov-lex (SK judicial decisions)
                                 · European Commission competition decisions
                                 · CJEU via EUR-Lex
  Step 3: analyze_case_law() - Analyse retrieved case law in context of the topic
  Step 4: apply_to_case()    - Apply the analysis systematically to the specific case facts

Input:  case_description (facts + legal questions), language
Output: {topic, case_law_sources, case_law_analysis, final_analysis, language, steps_completed}
"""
import json
import logging
from typing import Dict, List, Optional

from services.llm_client import llm_call
from services.external_search import search_all_sources
from config import cfg

logger = logging.getLogger(__name__)


# ============================================================
# Public entry point
# ============================================================

async def run_judge_analysis(
    case_description: str,
    language: str = "sk",
    conversation_id: Optional[str] = None,
) -> Dict:
    """
    Full 4-step AI Judge Assistant pipeline.

    Args:
        case_description: Facts of the case and legal questions posed
        language:         Response language - 'sk' | 'hu' | 'en'
        conversation_id:  Optional conversation reference for logging

    Returns:
        {
            "topic":               dict  - legal domain, issues, keywords, summary
            "case_law_sources":    list  - all retrieved citations with URLs
            "case_law_analysis":   str   - Step 3 narrative analysis
            "final_analysis":      str   - Step 4 application to the case
            "language":            str
            "steps_completed":     int   (4 on success)
        }
    """
    logger.info(f"[Judge] Starting analysis | lang={language} | conv={conversation_id}")

    # ── Step 1: Define the legal topic ──────────────────────────────────────
    topic = await _step1_define_topic(case_description, language)
    logger.info(
        f"[Judge] Step 1 complete | domain='{topic.get('legal_domain')}' "
        f"| jurisdictions={topic.get('jurisdictions')}"
    )

    # ── Step 2: Search external case law ────────────────────────────────────
    search_query = _build_search_query(topic)
    case_law_results = await _step2_search_case_law(search_query, topic)
    total_found = sum(len(v) for v in case_law_results.values())
    logger.info(f"[Judge] Step 2 complete | {total_found} results retrieved")

    # ── Step 3: Analyse case law ─────────────────────────────────────────────
    case_law_analysis = await _step3_analyze_case_law(topic, case_law_results, language)
    logger.info("[Judge] Step 3 complete | case law analysis done")

    # ── Step 4: Apply to the case ────────────────────────────────────────────
    final_analysis = await _step4_apply_to_case(
        case_description, topic, case_law_analysis, language
    )
    logger.info("[Judge] Step 4 complete | application to case done")

    # ── Build flat source list for the response ──────────────────────────────
    all_sources = _flatten_sources(case_law_results)

    return {
        "topic": topic,
        "case_law_sources": all_sources,
        "case_law_analysis": case_law_analysis,
        "final_analysis": final_analysis,
        "language": language,
        "steps_completed": 4,
    }


# ============================================================
# Step 1 – Topic definition
# ============================================================

async def _step1_define_topic(case_description: str, language: str) -> Dict:
    """
    Identify the legal domain, key issues, applicable jurisdictions,
    and generate search keywords for case law retrieval.
    """
    judge_prompts = cfg.prompts.get("judge_prompts", {})
    define_prompt = judge_prompts.get("define_topic", "").format(
        case_description=case_description
    )

    lang_context = {
        "sk": "Analyze primarily in Slovak law context. Slovak courts apply both [SK] national law and directly applicable [EU] EU law.",
        "hu": "Analyze in Slovak/Hungarian law context. Both [SK] Slovak law and [EU] EU law may apply.",
        "en": "Analyze in Slovak and EU law context. Identify whether [SK] Slovak, [EU] EU, or both jurisdictions apply.",
    }.get(language, "Analyze in Slovak and EU law context.")

    result = await llm_call(
        role="deep",
        messages=[
            {
                "role": "system",
                "content": (
                    "[LEGAL ANALYSIS REQUEST - Educational and Professional Purpose]\n"
                    "You are an expert Slovak and EU legal analyst assisting judges and "
                    "legal professionals with case preparation and legal research.\n"
                    f"{lang_context}\n"
                    "Return only valid JSON. No markdown, no explanation outside JSON."
                ),
            },
            {"role": "user", "content": define_prompt},
        ],
        response_format="json",
        max_tokens=800,
    )

    try:
        topic = json.loads(result["content"])
    except (json.JSONDecodeError, TypeError):
        logger.warning("[Judge] Topic definition JSON parse failed, using fallback")
        topic = {
            "legal_domain": "general law",
            "legal_issues": [case_description[:300]],
            "jurisdictions": ["SK", "EU"],
            "search_keywords": _extract_fallback_keywords(case_description),
            "topic_summary": case_description[:400],
        }

    # Ensure required keys have defaults
    topic.setdefault("legal_domain", "general law")
    topic.setdefault("legal_issues", [])
    topic.setdefault("jurisdictions", ["SK", "EU"])
    topic.setdefault("search_keywords", [])
    topic.setdefault("topic_summary", "")

    return topic


# ============================================================
# Step 2 – Case law search
# ============================================================

async def _step2_search_case_law(search_query: str, topic: Dict) -> Dict:
    """
    Search Slov-lex, EC Decisions, and CJEU in parallel.
    """
    jurisdictions = topic.get("jurisdictions", ["SK", "EU"])
    include_sk = "SK" in jurisdictions
    include_eu = "EU" in jurisdictions

    return await search_all_sources(
        query=search_query,
        max_per_source=5,
        include_sk=include_sk,
        include_ec=include_eu,
        include_cjeu=include_eu,
    )


# ============================================================
# Step 3 – Case law analysis
# ============================================================

async def _step3_analyze_case_law(
    topic: Dict,
    case_law_results: Dict,
    language: str,
) -> str:
    """
    Analyse the retrieved case law: identify principles, legal tests,
    hierarchy of norms, and gaps in existing precedent.
    """
    formatted = _format_case_law_results(case_law_results)

    if not formatted:
        logger.info("[Judge] No external case law found; returning notice")
        return _no_case_law_notice(language)

    judge_prompts = cfg.prompts.get("judge_prompts", {})
    analyze_prompt = judge_prompts.get("analyze_case_law", "").format(
        topic_summary=topic.get("topic_summary", ""),
        legal_issues=", ".join(topic.get("legal_issues", [])),
        case_law_results=formatted,
    )

    lang_suffix = judge_prompts.get("language_suffix", {}).get(language, "")
    analyze_prompt += lang_suffix

    result = await llm_call(
        role="deep",
        messages=[
            {
                "role": "system",
                "content": (
                    "[LEGAL ANALYSIS REQUEST - Educational and Professional Purpose]\n"
                    "You are a senior legal analyst specialising in Slovak and EU law. "
                    "Provide objective, accurate analysis of the retrieved case law for "
                    "legal professionals engaged in case preparation. "
                    "Label every source reference with [SK] or [EU]."
                ),
            },
            {"role": "user", "content": analyze_prompt},
        ],
        max_tokens=2500,
    )

    return result["content"]


# ============================================================
# Step 4 – Application to the case
# ============================================================

async def _step4_apply_to_case(
    case_description: str,
    topic: Dict,
    case_law_analysis: str,
    language: str,
) -> str:
    """
    Systematically apply the identified case law to the specific facts,
    following a structured judicial analysis format.
    """
    judge_prompts = cfg.prompts.get("judge_prompts", {})
    apply_prompt = judge_prompts.get("apply_to_case", "").format(
        case_description=case_description,
        topic_analysis=json.dumps(topic, ensure_ascii=False, indent=2),
        case_law_analysis=case_law_analysis,
    )

    lang_suffix = judge_prompts.get("language_suffix", {}).get(language, "")
    apply_prompt += lang_suffix

    result = await llm_call(
        role="deep",
        messages=[
            {
                "role": "system",
                "content": (
                    "[LEGAL ANALYSIS REQUEST - Educational and Professional Purpose]\n"
                    "You are a senior judge/legal analyst preparing a thorough legal "
                    "opinion for professional legal proceedings. This analysis is for "
                    "legal research and educational purposes. "
                    "Structure your analysis clearly with headings. "
                    "Label every source citation with [SK] or [EU]. "
                    "Distinguish between binding precedent and persuasive authority. "
                    "Note where Slovak law must be interpreted in conformity with EU law."
                ),
            },
            {"role": "user", "content": apply_prompt},
        ],
        max_tokens=4000,
    )

    return result["content"]


# ============================================================
# Helpers
# ============================================================

def _build_search_query(topic: Dict) -> str:
    """Build an optimised search query from topic keywords."""
    keywords = topic.get("search_keywords", [])
    if not keywords:
        # Fall back to topic summary words
        summary = topic.get("topic_summary", "")
        keywords = summary.split()[:8]
    # Use first 6 keywords to keep query focused
    return " ".join(str(k) for k in keywords[:6])


def _extract_fallback_keywords(text: str) -> List[str]:
    """Extract simple keywords from text when LLM JSON parsing fails."""
    import re
    # Remove punctuation, split, deduplicate, return up to 8 meaningful words
    words = re.findall(r'\b[a-zA-ZáäčďéíľĺňóôŕšťúýžÁÄČĎÉÍĽĹŇÓÔŔŠŤÚÝŽ]{4,}\b', text)
    seen: set = set()
    result = []
    for w in words:
        if w.lower() not in seen:
            seen.add(w.lower())
            result.append(w)
        if len(result) >= 8:
            break
    return result


def _format_case_law_results(case_law_results: Dict) -> str:
    """
    Format retrieved case law into a structured string for LLM prompts.
    Returns empty string if nothing was found.
    """
    source_headers = {
        "slov_lex":     "=== Slov-lex [SK] – Slovak Judicial Decisions ===",
        "ec_decisions": "=== European Commission [EU] – Competition Decisions ===",
        "cjeu":         "=== CJEU / EUR-Lex [EU] – Court of Justice of the EU ===",
    }

    parts = []
    for source_key, items in case_law_results.items():
        if not items:
            continue

        header = source_headers.get(source_key, f"=== {source_key} ===")
        parts.append(header)

        for item in items:
            title = item.get("title", "")
            case_num = item.get("case_number", "")
            date = item.get("date", "")
            url = item.get("url", "")
            summary = item.get("summary", "")

            line = f"• {title}"
            if case_num:
                line += f"  [{case_num}]"
            if date:
                line += f"  ({date})"
            if url:
                line += f"\n  URL: {url}"
            if summary:
                line += f"\n  Summary: {summary[:400]}"

            parts.append(line)

        parts.append("")  # blank line between sections

    return "\n".join(parts)


def _flatten_sources(case_law_results: Dict) -> List[Dict]:
    """Flatten the per-source results into a single list for the API response."""
    sources = []
    for items in case_law_results.values():
        for item in items:
            sources.append({
                "title": item.get("title", ""),
                "case_number": item.get("case_number", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "jurisdiction": item.get("jurisdiction", ""),
                "date": item.get("date", ""),
            })
    return sources


def _no_case_law_notice(language: str) -> str:
    """Return a multilingual notice when no case law was retrieved."""
    notices = {
        "sk": (
            "Z externých databáz (Slov-lex, Európska komisia, Súdny dvor EÚ) "
            "neboli pre danú tému nájdené žiadne konkrétne súdne rozhodnutia. "
            "Analýza bude vychádzať zo všeobecných právnych zásad a platnej legislatívy "
            "aplikovateľnej na danú právnu oblasť."
        ),
        "hu": (
            "A külső adatbázisokból (Slov-lex, Európai Bizottság, EU Bírósága) "
            "nem találtunk konkrét ítéleteket erre a témára. "
            "Az elemzés az alkalmazandó általános jogelveken és hatályos jogszabályokon alapul."
        ),
        "en": (
            "No specific case law was retrieved from the external databases "
            "(Slov-lex, European Commission, Court of Justice of the EU) for this topic. "
            "The analysis will be based on general legal principles and applicable legislation "
            "for this area of law."
        ),
    }
    return notices.get(language, notices["en"])
