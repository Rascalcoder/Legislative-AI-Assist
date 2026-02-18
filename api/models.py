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
    chunk_id: str
    document_id: str
    jurisdiction: Optional[str] = None
    jurisdiction_label: str = ""
    rrf_score: float = 0
    content_preview: str = ""


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


# ============================================================
# Judge Assistant
# ============================================================

class JudgeAnalysisRequest(BaseModel):
    """Request to run the AI Judge Assistant 4-step analysis pipeline."""
    case_description: str = Field(
        ...,
        description=(
            "Full description of the case: facts, parties, legal questions to resolve. "
            "Minimum 50 characters. Supports Slovak, Hungarian, and English."
        ),
        min_length=50,
    )
    language: Optional[str] = Field(
        None,
        description="Response language: 'sk' (Slovak), 'hu' (Hungarian), 'en' (English). "
                    "Auto-detected from case_description if omitted.",
    )
    conversation_id: Optional[str] = Field(
        None,
        description="Optional conversation reference for audit logging.",
    )


class TopicDefinition(BaseModel):
    """Step 1 output – identified legal topic and search parameters."""
    legal_domain: str = Field("", description="Primary area of law (e.g. competition law, administrative law)")
    legal_issues: List[str] = Field(default_factory=list, description="Key legal questions to resolve")
    jurisdictions: List[str] = Field(default_factory=list, description="Applicable jurisdictions: SK, EU, or both")
    search_keywords: List[str] = Field(default_factory=list, description="Keywords used to search case law databases")
    topic_summary: str = Field("", description="Concise professional summary of the legal topic")


class CaseLawSource(BaseModel):
    """A single case law citation retrieved from an external database."""
    title: str = Field("", description="Title or name of the decision/judgment")
    case_number: str = Field("", description="Case reference number (e.g. C-123/45, AT.40099)")
    url: str = Field("", description="URL to the full text in the source database")
    source: str = Field("", description="Database name: Slov-lex | EC Competition Decisions | CJEU / EUR-Lex")
    jurisdiction: str = Field("", description="SK or EU")
    date: str = Field("", description="Date of the decision/judgment")


class JudgeAnalysisResponse(BaseModel):
    """Full response from the 4-step AI Judge Assistant pipeline."""
    topic: TopicDefinition = Field(..., description="Step 1: identified legal topic")
    case_law_sources: List[CaseLawSource] = Field(
        default_factory=list,
        description="Step 2: case law retrieved from Slov-lex, EC Decisions, and CJEU",
    )
    case_law_analysis: str = Field(
        "", description="Step 3: analysis of retrieved case law – principles and legal tests"
    )
    final_analysis: str = Field(
        "", description="Step 4: application of case law to the specific case facts"
    )
    language: str = Field("sk", description="Language of the analysis")
    steps_completed: int = Field(4, description="Number of pipeline steps completed (max 4)")
    conversation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
