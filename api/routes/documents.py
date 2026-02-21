"""Document management endpoints with jurisdiction tagging."""
import logging
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Form

from api.models import DocumentUploadResponse
from services.document_service import upload_and_process
from services import supabase_service as db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("legal"),
    language: Optional[str] = Form(None),
    jurisdiction: Optional[str] = Form(None),
    source_id: Optional[str] = Form(None),
):
    """Upload legal document (PDF, DOCX, TXT) with jurisdiction tag."""
    allowed = [".pdf", ".docx", ".doc", ".txt"]
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed)}",
        )

    try:
        result = await upload_and_process(
            file=file,
            document_type=document_type,
            language=language,
            jurisdiction=jurisdiction,
            source_id=source_id,
        )

        return DocumentUploadResponse(
            document_id=result["document_id"],
            filename=file.filename,
            status="processed",
            chunks_processed=result["chunks_processed"],
        )

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    language: Optional[str] = None,
    jurisdiction: Optional[str] = None,
):
    """List documents with optional filtering."""
    return db.list_documents(skip=skip, limit=limit, language=language, jurisdiction=jurisdiction)


@router.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get document metadata."""
    doc = db.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete document and all chunks."""
    db.delete_document(document_id)
    return {"message": "Document deleted"}




