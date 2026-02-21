"""
Chat service - orchestrates the 3-function pipeline.
All state stored in Supabase (no in-memory dicts).

Flow: F1 (Router) -> F2 (Retrieval) -> F3 (Generate+Verify)
"""
import logging
from typing import Dict, Optional

from services import supabase_service as db
from services.language_service import LanguageService
from services.llm_client import llm_call
from pipeline.router import route
from pipeline.retrieval import retrieve
from pipeline.generate import generate_and_verify
from config import cfg

logger = logging.getLogger(__name__)
lang_service = LanguageService()


async def process_chat(
    message: str,
    conversation_id: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict:
    """
    Full chat pipeline: Route -> Retrieve -> Generate+Verify.

    Returns:
        {response, conversation_id, sources, confidence, language, verified}
    """
    if not language:
        language = lang_service.detect_language(message)

    if not conversation_id:
        conversation_id = db.create_conversation(language)

    # Load conversation history from Supabase
    history = db.get_conversation_messages(conversation_id)

    # F1: Route
    routing = await route(message, history)
    logger.info(
        f"Route: intent={routing['intent']}, "
        f"complexity={routing.get('complexity')}"
    )

    # Handle non-search intents (greetings, offtopic)
    if routing.get("skip_search"):
        return await _handle_simple(
            message, conversation_id, language, routing["intent"]
        )

    # F2: Retrieve
    chunks = await retrieve(
        query=routing.get("rewritten_query", message),
        needs_eu=routing.get("needs_eu", True),
        needs_sk=routing.get("needs_sk", True),
        language=language,
    )

    # F3: Generate + Verify
    result = await generate_and_verify(
        query=message,
        chunks=chunks,
        language=language,
        conversation_history=history,
        complexity=routing.get("complexity", "simple"),
    )

    # Save messages to Supabase
    db.add_message(conversation_id, "user", message, language=language)
    db.add_message(
        conversation_id,
        "assistant",
        result["response"],
        sources=result["sources"],
        confidence=result["confidence"],
        language=language,
        model_used=result["model_used"],
        token_count=result["output_tokens"],
    )

    # Audit log
    db.log_audit(
        action="chat",
        model=result["model_used"],
        provider=result.get("provider"),
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
        latency_ms=result["latency_ms"],
        metadata={
            "intent": routing["intent"],
            "complexity": routing.get("complexity"),
            "chunks_used": len(chunks),
            "verified": result["verified"],
        },
    )

    return {
        "response": result["response"],
        "conversation_id": conversation_id,
        "sources": result["sources"],
        "confidence": result["confidence"],
        "language": language,
        "verified": result["verified"],
    }


async def _handle_simple(
    message: str,
    conversation_id: str,
    language: str,
    intent: str,
) -> Dict:
    """Handle greetings and offtopic without retrieval."""
    if intent == "greeting":
        response_text = cfg.prompts["greeting_response"].get(language, "Hello!")
    elif intent == "offtopic":
        response_text = cfg.prompts["offtopic_response"].get(
            language, "I specialize in competition law only."
        )
    else:
        base = cfg.prompts["system_prompts"]["base"]
        suffix = cfg.prompts["system_prompts"]["language_suffix"].get(language, "")
        result = await llm_call(
            role="light",
            messages=[
                {"role": "system", "content": base + suffix},
                {"role": "user", "content": message},
            ],
            max_tokens=500,
        )
        response_text = result["content"]

    db.add_message(conversation_id, "user", message, language=language)
    db.add_message(conversation_id, "assistant", response_text, language=language)

    return {
        "response": response_text,
        "conversation_id": conversation_id,
        "sources": [],
        "confidence": 0.0,
        "language": language,
        "verified": True,
    }




