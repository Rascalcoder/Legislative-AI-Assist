"""Health check endpoint."""
from datetime import datetime, timezone
from fastapi import APIRouter
from api.models import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check."""
    return HealthResponse(
        status="healthy",
        version="2.0.0",
        timestamp=datetime.now(timezone.utc),
        supported_languages=["sk", "hu", "en"],
    )




