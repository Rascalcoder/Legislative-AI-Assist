"""Hybrid search endpoints - vector + FTS with jurisdiction filtering."""
import logging
from fastapi import APIRouter, HTTPException

from api.models import SearchRequest, SearchResponse, SearchResultItem
from services.search_service import search

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(request: SearchRequest):
    """Hybrid search across SK + EU competition law documents."""
    try:
        results = await search(
            query=request.query,
            language=request.language,
            top_k=request.top_k,
            jurisdiction=request.jurisdiction,
        )

        return SearchResponse(
            query=request.query,
            language=results["language"],
            results=[
                SearchResultItem(
                    chunk_id=r["chunk_id"],
                    document_id=r["document_id"],
                    content=r["content"],
                    jurisdiction=r.get("jurisdiction"),
                    jurisdiction_label=r.get("jurisdiction_label", ""),
                    rrf_score=r.get("rrf_score", 0),
                    metadata=r.get("metadata", {}),
                )
                for r in results["results"]
            ],
            total_results=len(results["results"]),
        )

    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

