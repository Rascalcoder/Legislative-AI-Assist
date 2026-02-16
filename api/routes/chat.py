"""Chat endpoints - competition law AI assistant."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from api.models import ChatRequest, ChatResponse, SourceInfo
from services.chat_service import process_chat
from services import supabase_service as db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat with competition law AI assistant (SK + EU)."""
    try:
        result = await process_chat(
            message=request.message,
            conversation_id=request.conversation_id,
            language=request.language,
        )

        return ChatResponse(
            response=result["response"],
            conversation_id=result["conversation_id"],
            language=result["language"],
            sources=[SourceInfo(**s) for s in result.get("sources", [])],
            confidence=result.get("confidence", 0.0),
            verified=result.get("verified", True),
            timestamp=datetime.now(timezone.utc),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/history/{conversation_id}")
async def get_chat_history(conversation_id: str):
    """Get conversation history."""
    messages = db.get_conversation_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@router.delete("/chat/history/{conversation_id}")
async def delete_chat_history(conversation_id: str):
    """Delete conversation history."""
    db.delete_conversation(conversation_id)
    return {"message": "Conversation deleted"}

