"""
Centralized Pydantic request/response models for all API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============================================================
# Chat
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message in any language")
    conversation_id: Optional[str] = None
    language: Optional[str] = None


class SourceInfo(BaseModel):
    # Common fields
    jurisdiction: Optional[str] = None
    jurisdiction_label: str = ""
    type: str = "document"  # 'document' or 'court_case'
    
    # Document chunk fields (when type='document')
    chunk_id: Optional[str] = None
    document_id: Optional[str] = None
    rrf_score: Optional[float] = 0
    content_preview: Optional[str] = ""
    
    # Court case fields (when type='court_case')
    case_number: Optional[str] = None
    url: Optional[str] = None
    court: Optional[str] = None
    date: Optional[str] = None
    title: Optional[str] = None
    relevance_score: Optional[float] = 0


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    language: str
    sources: List[SourceInfo] = []
    confidence: float
    verified: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


# ============================================================
# Search
# ============================================================

class SearchRequest(BaseModel):
    query: str
    language: Optional[str] = None
    top_k: int = Field(5, ge=1, le=50)
    jurisdiction: Optional[str] = Field(
        None, description="SK, EU, or null for both"
    )


class SearchResultItem(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    jurisdiction: Optional[str] = None
    jurisdiction_label: str = ""
    rrf_score: float = 0
    metadata: dict = {}


class SearchResponse(BaseModel):
    query: str
    language: str
    results: List[SearchResultItem]
    total_results: int


# ============================================================
# Documents
# ============================================================

class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    chunks_processed: int


class DocumentMeta(BaseModel):
    id: str
    filename: str
    document_type: str
    language: str
    jurisdiction: Optional[str] = None
    upload_date: Optional[datetime] = None
    size_bytes: Optional[int] = None
    status: str = "processing"
    chunk_count: int = 0


# ============================================================
# Health
# ============================================================

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    supported_languages: List[str]
