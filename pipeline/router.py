"""
F1: Router - Rule-based triage + LLM intent classification + query rewrite.

L0: Deterministic rules (no LLM call) - greetings, offtopic detection
L1: LLM-based intent classification and query rewriting (light model)

Input:  raw user query + conversation context
Output: {intent, complexity, needs_eu, needs_sk, rewritten_query, language, skip_search}
"""
import json
import logging
import re
from typing import Dict, List, Optional

from services.llm_client import llm_call
from services.language_service import LanguageService
from services.supabase_service import log_audit
from config import cfg

logger = logging.getLogger(__name__)
lang_service = LanguageService()

# L0: Rule-based patterns (no LLM call needed)
GREETING_PATTERNS = {
    "hello", "hi", "hey", "good morning", "good afternoon",
    "ahoj", "dobry den", "dobré ráno",
    "szia", "helló", "jó napot", "jó reggelt",
}

OFFTOPIC_PATTERNS = {
    "weather", "recipe", "sport", "football", "movie", "music",
    "počasie", "recept", "futbal", "film", "hudba",
    "időjárás", "recept", "foci", "film", "zene",
}


async def route(query: str, conversation_history: Optional[List[Dict]] = None) -> Dict:
    """
    Classify query and prepare for search.

    Returns:
        {
            "intent": str,          # question|search|followup|greeting|offtopic
            "complexity": str,      # simple|complex
            "needs_eu": bool,
            "needs_sk": bool,
            "rewritten_query": str, # optimized for search
            "language": str,        # sk|hu|en
            "skip_search": bool,    # True = no retrieval needed
        }
    """
    language = lang_service.detect_language(query)
    query_lower = query.lower().strip()

    # L0: Rule-based fast-path
    # Use word-boundary matching to avoid false positives
    # e.g. "hi" must not match inside "prohibition", "this", "which"
    def _has_word(text: str, patterns: set) -> bool:
        for p in patterns:
            if re.search(r"\b" + re.escape(p) + r"\b", text):
                return True
        return False

    # Only match if query is short (≤6 words) — long queries are almost never greetings
    if len(query_lower.split()) <= 6 and _has_word(query_lower, GREETING_PATTERNS):
        return {
            "intent": "greeting",
            "complexity": "simple",
            "needs_eu": False,
            "needs_sk": False,
            "rewritten_query": query,
            "language": language,
            "skip_search": True,
        }

    if len(query_lower.split()) <= 4 and _has_word(query_lower, OFFTOPIC_PATTERNS):
        return {
            "intent": "offtopic",
            "complexity": "simple",
            "needs_eu": False,
            "needs_sk": False,
            "rewritten_query": query,
            "language": language,
            "skip_search": True,
        }

    # L1: LLM intent classification (uses 'light' model)
    context_summary = ""
    if conversation_history:
        last_msgs = conversation_history[-4:]  # last 2 exchanges
        context_summary = "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in last_msgs
        )

    router_prompt = cfg.prompts["router_prompt"].format(
        query=query,
        context=context_summary or "No previous context.",
    )

    result = await llm_call(
        role="light",
        messages=[
            {
                "role": "system",
                "content": "You are a query classifier for a legal competition law database used by legal professionals for compliance and research. Return valid JSON only.",
            },
            {"role": "user", "content": router_prompt},
        ],
        response_format="json",
        max_tokens=300,
    )

    log_audit(
        action="router",
        model=result.get("model"),
        provider=result.get("provider"),
        input_tokens=result.get("input_tokens"),
        output_tokens=result.get("output_tokens"),
        latency_ms=result.get("latency_ms"),
        metadata={"query_length": len(query)},
    )

    try:
        classification = json.loads(result["content"])
    except json.JSONDecodeError:
        logger.warning("Router failed to parse JSON, using defaults")
        classification = {
            "intent": "question",
            "complexity": "simple",
            "needs_eu": True,
            "needs_sk": True,
            "rewritten_query": query,
        }

    # Ensure required fields
    classification.setdefault("intent", "question")
    classification.setdefault("complexity", "simple")
    classification.setdefault("needs_eu", True)
    classification.setdefault("needs_sk", True)
    classification.setdefault("rewritten_query", query)
    classification["language"] = language
    classification["skip_search"] = classification["intent"] in ("greeting", "offtopic")

    logger.info(
        f"Router: intent={classification['intent']}, "
        f"complexity={classification['complexity']}, "
        f"eu={classification['needs_eu']}, sk={classification['needs_sk']}"
    )

    return classification
