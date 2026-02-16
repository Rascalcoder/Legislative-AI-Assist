"""
F2: Retrieval - Hybrid search (pgvector + FTS with RRF fusion).

Input:  rewritten_query, needs_eu, needs_sk, language
Output: ranked list of chunks with [EU]/[SK] labels

Uses Supabase hybrid_search RPC function which combines:
- Vector similarity search (pgvector, cosine distance)
- Full-text search (PostgreSQL tsvector, BM25-like)
- Reciprocal Rank Fusion (RRF) to merge results
"""
import logging
from typing import Dict, List, Optional

from services.llm_client import embed
from services import supabase_service as db
from config import cfg

logger = logging.getLogger(__name__)


async def retrieve(
    query: str,
    needs_eu: bool = True,
    needs_sk: bool = True,
    language: Optional[str] = None,
    top_k: Optional[int] = None,
) -> List[Dict]:
    """
    Perform hybrid search across jurisdictions.

    Returns list of chunks, each with:
        chunk_id, document_id, content, jurisdiction,
        jurisdiction_label, language, metadata, rrf_score,
        vector_rank, fts_rank
    """
    top_k = top_k or cfg.search.get("final_top_k", 5)

    # Generate query embedding
    query_embedding = await embed(query)

    results = []

    # Determine which jurisdictions to search
    jurisdictions = []
    if needs_sk:
        jurisdictions.append("SK")
    if needs_eu:
        jurisdictions.append("EU")
    if not jurisdictions:
        jurisdictions = [None]  # search all

    for jurisdiction in jurisdictions:
        search_results = db.hybrid_search(
            query_embedding=query_embedding,
            query_text=query,
            match_count=top_k,
            jurisdiction=jurisdiction,
            language=None,  # cross-lingual (embeddings handle it)
        )

        for r in search_results:
            label = f"[{r['jurisdiction']}]" if r.get("jurisdiction") else ""
            results.append({
                "chunk_id": r["chunk_id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "jurisdiction": r.get("jurisdiction"),
                "jurisdiction_label": label,
                "language": r.get("language"),
                "metadata": r.get("metadata", {}),
                "rrf_score": r.get("rrf_score", 0),
                "vector_rank": r.get("vector_rank"),
                "fts_rank": r.get("fts_rank"),
            })

    # Sort by RRF score, take top_k
    results.sort(key=lambda x: x["rrf_score"], reverse=True)
    results = results[:top_k]

    logger.info(f"Retrieved {len(results)} chunks for: '{query[:80]}...'")
    return results
