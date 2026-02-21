"""
Search service - hybrid search endpoint wrapper.
Uses Supabase pgvector + FTS via hybrid_search RPC.
"""
import logging
from typing import Dict, Optional

from services.llm_client import embed
from services import supabase_service as db
from services.language_service import LanguageService

logger = logging.getLogger(__name__)
lang_service = LanguageService()


async def search(
    query: str,
    language: Optional[str] = None,
    top_k: int = 5,
    jurisdiction: Optional[str] = None,
) -> Dict:
    """Hybrid search endpoint."""
    if not language:
        language = lang_service.detect_language(query)

    query_embedding = await embed(query)

    results = db.hybrid_search(
        query_embedding=query_embedding,
        query_text=query,
        match_count=top_k,
        jurisdiction=jurisdiction,
    )

    formatted = []
    for r in results:
        label = f"[{r.get('jurisdiction', '')}]" if r.get("jurisdiction") else ""
        formatted.append({
            "chunk_id": str(r["chunk_id"]),
            "document_id": str(r["document_id"]),
            "content": r["content"],
            "jurisdiction": r.get("jurisdiction"),
            "jurisdiction_label": label,
            "rrf_score": r.get("rrf_score", 0),
            "metadata": r.get("metadata", {}),
        })

    return {"language": language, "results": formatted}




