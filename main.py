"""Legislative AI Assist - Competition Law Assistant (SK + EU)."""
import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import chat, documents, search, health, monitoring

# stdout logging (Cloud Run collects automatically)
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Legislative AI Assist...")
    yield
    logger.info("Shutting down...")


app = FastAPI(
    title="Legislative AI Assist",
    description="Competition law assistant - SK + EU",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration - secure for production
# Set ALLOWED_ORIGINS env var with comma-separated list of allowed origins
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # Production: use specific domains from environment variable
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    logger.info(f"CORS enabled for specific origins: {allowed_origins}")
else:
    # Development: allow localhost and common dev ports
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
    ]
    logger.warning("CORS: No ALLOWED_ORIGINS set, using development defaults")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(search.router, prefix="/api/v1", tags=["Search"])
app.include_router(monitoring.router, prefix="/api/v1", tags=["Monitoring"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

