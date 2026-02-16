"""
Document processing - extract text, chunk, embed, store in Supabase.
Chunking logic reused from original. Storage goes to Supabase.
"""
import io
import logging
from typing import Optional, Dict, List

from fastapi import UploadFile
import PyPDF2
from docx import Document

from services.llm_client import embed_batch
from services import supabase_service as db
from services.language_service import LanguageService
from config import cfg

logger = logging.getLogger(__name__)
lang_service = LanguageService()


def chunk_text(text: str) -> List[str]:
    """Split text into chunks with overlap. Breaks at sentence boundaries."""
    chunk_size = cfg.search.get("chunk_size", 1000)
    overlap = cfg.search.get("chunk_overlap", 200)

    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Break at sentence boundary
        if end < len(text):
            last_period = chunk.rfind(".")
            last_newline = chunk.rfind("\n")
            break_point = max(last_period, last_newline)

            if break_point > chunk_size * 0.5:
                chunk = chunk[: break_point + 1]
                end = start + break_point + 1

        chunks.append(chunk.strip())
        start = end - overlap

    return [c for c in chunks if c]


def extract_text(filename: str, file_content: bytes) -> str:
    """Extract text from uploaded file."""
    fname = filename.lower()
    if fname.endswith(".pdf"):
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        return "\n".join(page.extract_text() for page in reader.pages).strip()
    elif fname.endswith((".docx", ".doc")):
        doc = Document(io.BytesIO(file_content))
        return "\n".join(p.text for p in doc.paragraphs).strip()
    elif fname.endswith(".txt"):
        return file_content.decode("utf-8").strip()
    else:
        raise ValueError(f"Unsupported file type: {filename}")


async def upload_and_process(
    file: UploadFile,
    document_type: str = "legal",
    language: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    source_id: Optional[str] = None,
) -> Dict:
    """Upload, chunk, embed, and store document in Supabase."""
    file_content = await file.read()
    text = extract_text(file.filename, file_content)

    if not language:
        language = lang_service.detect_language(text[:1000])

    # Insert document record
    doc_id = db.insert_document(
        filename=file.filename,
        document_type=document_type,
        language=language,
        size_bytes=len(file_content),
        jurisdiction=jurisdiction,
        source_id=source_id,
    )

    try:
        # Chunk
        chunks = chunk_text(text)
        logger.info(f"Created {len(chunks)} chunks from {file.filename}")

        # Embed (batch)
        embeddings = await embed_batch(chunks)

        # Prepare chunk records
        chunk_records = []
        for i, (chunk_text_item, emb) in enumerate(zip(chunks, embeddings)):
            chunk_records.append({
                "document_id": doc_id,
                "chunk_index": i,
                "content": chunk_text_item,
                "embedding": emb,
                "language": language,
                "jurisdiction": jurisdiction,
                "metadata": {
                    "filename": file.filename,
                    "document_type": document_type,
                    "source_id": source_id,
                },
            })

        # Insert all chunks
        db.insert_chunks(chunk_records)

        # Update document status
        db.update_document_status(doc_id, "processed", len(chunks))

        logger.info(f"Document processed: {doc_id} ({len(chunks)} chunks)")
        return {"document_id": doc_id, "chunks_processed": len(chunks)}

    except Exception as e:
        db.update_document_status(doc_id, "error", 0)
        logger.error(f"Document processing error: {e}")
        raise

