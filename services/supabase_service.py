"""
Supabase service - all database operations in one place.
Tables: documents, chunks, conversations, messages, audit_log
Hybrid search via RPC function.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

from supabase import create_client, Client
from config import cfg

logger = logging.getLogger(__name__)

# Module-level singleton
_client: Optional[Client] = None


def _get_client() -> Client:
    """Lazy-init Supabase client."""
    global _client
    if _client is None:
        _client = create_client(cfg.supabase_url, cfg.supabase_key)
        logger.info("Supabase client initialized")
    return _client


# ============================================================
# Documents
# ============================================================

def insert_document(
    filename: str,
    document_type: str,
    language: str,
    size_bytes: int,
    jurisdiction: Optional[str] = None,
    source_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Insert document metadata, return document ID."""
    doc_id = str(uuid.uuid4())
    data = {
        "id": doc_id,
        "filename": filename,
        "document_type": document_type,
        "language": language,
        "size_bytes": size_bytes,
        "jurisdiction": jurisdiction,
        "source_id": source_id,
        "status": "processing",
        "metadata": metadata or {},
    }
    _get_client().table("documents").insert(data).execute()
    logger.info(f"Document inserted: {doc_id} ({filename})")
    return doc_id


def update_document_status(doc_id: str, status: str, chunk_count: int = 0):
    """Update document processing status."""
    _get_client().table("documents").update({
        "status": status,
        "chunk_count": chunk_count,
    }).eq("id", doc_id).execute()


def list_documents(
    skip: int = 0,
    limit: int = 100,
    language: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> List[Dict]:
    """List documents with optional filtering."""
    query = _get_client().table("documents").select("*")
    if language:
        query = query.eq("language", language)
    if jurisdiction:
        query = query.eq("jurisdiction", jurisdiction)
    result = query.range(skip, skip + limit - 1).order("created_at", desc=True).execute()
    return result.data


def get_document(doc_id: str) -> Optional[Dict]:
    """Get document by ID."""
    result = _get_client().table("documents").select("*").eq("id", doc_id).execute()
    return result.data[0] if result.data else None


def delete_document(doc_id: str):
    """Delete document and all its chunks (cascade)."""
    _get_client().table("documents").delete().eq("id", doc_id).execute()
    logger.info(f"Document deleted: {doc_id}")


# ============================================================
# Chunks
# ============================================================

def insert_chunks(chunks: List[Dict]):
    """Batch insert chunks with embeddings."""
    _get_client().table("chunks").insert(chunks).execute()
    logger.info(f"Inserted {len(chunks)} chunks")


# ============================================================
# Hybrid Search
# ============================================================

def hybrid_search(
    query_embedding: List[float],
    query_text: str,
    match_count: int = 5,
    jurisdiction: Optional[str] = None,
    language: Optional[str] = None,
) -> List[Dict]:
    """Call the hybrid_search RPC function (vector + FTS + RRF)."""
    params = {
        "query_embedding": query_embedding,
        "query_text": query_text,
        "match_count": match_count,
        "vector_weight": cfg.search.get("vector_weight", 0.6),
        "fts_weight": cfg.search.get("fts_weight", 0.4),
        "rrf_k": cfg.search.get("rrf_k", 60),
        "filter_jurisdiction": jurisdiction,
        "filter_language": language,
    }
    result = _get_client().rpc("hybrid_search", params).execute()
    return result.data


# ============================================================
# Conversations
# ============================================================

def create_conversation(language: str = "en") -> str:
    """Create a new conversation, return ID."""
    conv_id = str(uuid.uuid4())
    _get_client().table("conversations").insert({
        "id": conv_id,
        "language": language,
    }).execute()
    return conv_id


def get_conversation_messages(conv_id: str, limit: int = 20) -> List[Dict]:
    """
    Get recent messages for a conversation (chronological order).
    
    Args:
        conv_id: Conversation UUID
        limit: Max messages to retrieve (default: 20 = 10 exchanges)
        
    Returns:
        List of messages in chronological order (oldest first)
    """
    result = (
        _get_client()
        .table("messages")
        .select("*")
        .eq("conversation_id", conv_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Reverse to get chronological order (oldest to newest)
    messages = list(reversed(result.data))
    return messages


def add_message(
    conv_id: str,
    role: str,
    content: str,
    sources: Optional[list] = None,
    confidence: Optional[float] = None,
    language: Optional[str] = None,
    model_used: Optional[str] = None,
    token_count: Optional[int] = None,
):
    """Add a message to a conversation."""
    data = {
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "sources": sources or [],
        "confidence": confidence,
        "language": language,
        "model_used": model_used,
        "token_count": token_count,
    }
    _get_client().table("messages").insert(data).execute()

    # Update conversation timestamp
    _get_client().table("conversations").update({
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", conv_id).execute()


def delete_conversation(conv_id: str):
    """Delete conversation and all its messages (cascade)."""
    _get_client().table("conversations").delete().eq("id", conv_id).execute()


# ============================================================
# Audit Log
# ============================================================

_COST_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
    "gemini-2.0-flash-lite": {"input": 0.0000375, "output": 0.00015},
    "text-embedding-3-large": {"input": 0.00013, "output": 0},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_PER_1K.get(model, {"input": 0.001, "output": 0.002})
    return (input_tokens / 1000 * rates["input"]) + (output_tokens / 1000 * rates["output"])


def log_audit(
    action: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    cost_usd: Optional[float] = None,
    latency_ms: Optional[int] = None,
    metadata: Optional[dict] = None,
):
    """Log an action to the audit trail with auto cost calculation."""
    if cost_usd is None and model and input_tokens is not None and output_tokens is not None:
        cost_usd = _estimate_cost(model, input_tokens, output_tokens)

    try:
        _get_client().table("audit_log").insert({
            "action": action,
            "model": model,
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost_usd, 6) if cost_usd else None,
            "latency_ms": latency_ms,
            "metadata": metadata or {},
        }).execute()
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
