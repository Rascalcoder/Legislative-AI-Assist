"""
F2: Retrieval - Hybrid search (pgvector + FTS with RRF fusion) + Live case scraping.

Input:  rewritten_query, needs_eu, needs_sk, language
Output: ranked list of chunks with [EU]/[SK] labels + real court case URLs

Uses Supabase hybrid_search RPC function which combines:
- Vector similarity search (pgvector, cosine distance)
- Full-text search (PostgreSQL tsvector, BM25-like)
- Reciprocal Rank Fusion (RRF) to merge results

PLUS: Live court case scraping from:
- NSSUD (Najvyšší správny súd SR) for SK cases
- PMÚ (Protimonopolný úrad SR) for SK authority decisions
- EUR-Lex (CJEU judgments) + EU Commission decisions for EU cases
"""
import logging
from typing import Dict, List, Optional

from services.llm_client import embed
from services import supabase_service as db
from services.case_retrieval import get_case_service
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


async def retrieve_with_cases(
    query: str,
    needs_eu: bool = True,
    needs_sk: bool = True,
    language: Optional[str] = None,
    top_k: Optional[int] = None,
    include_live_cases: bool = True,
) -> Dict:
    """
    Enhanced retrieval with live court case scraping.
    
    Returns both:
    1. Supabase hybrid search results (pre-indexed documents)
    2. Live court cases from external sources (NSSUD, etc.)
    
    Args:
        query: User query
        needs_eu: Include EU sources
        needs_sk: Include SK sources
        language: Query language
        top_k: Max results
        include_live_cases: Whether to scrape live cases (default: True)
        
    Returns:
        {
            "chunks": [...],  # Supabase results
            "cases": [...],   # Live court cases with URLs
            "total_sources": int
        }
    """
    top_k = top_k or cfg.search.get("final_top_k", 5)
    # Enterprise: fetch up to 50 live cases per jurisdiction (independent of chunk top_k)
    CASE_LIMIT = 50

    # 1. Get Supabase hybrid search results
    chunks = await retrieve(query, needs_eu, needs_sk, language, top_k)

    # 2. Get live court cases (if enabled)
    cases = []
    if include_live_cases:
        try:
            case_service = get_case_service()

            # Determine jurisdiction
            jurisdiction = None
            if needs_sk and not needs_eu:
                jurisdiction = "SK"
            elif needs_eu and not needs_sk:
                jurisdiction = "EU"
            # else: both (jurisdiction=None)

            cases = await case_service.search_cases(
                query=query,
                jurisdiction=jurisdiction,
                limit=CASE_LIMIT,
            )

            logger.info(f"Retrieved {len(cases)} live court cases")

        except Exception as e:
            logger.error(f"Error retrieving live cases: {e}")
            cases = []
    
    return {
        "chunks": chunks,
        "cases": cases,
        "total_sources": len(chunks) + len(cases),
    }
