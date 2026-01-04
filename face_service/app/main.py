"""
FastAPI application for Face Recognition Service.

Provides endpoints for face detection, embedding generation,
and liveness detection with model preloading on startup.
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.api.v1.router import api_router
from app.core.config import settings
from app.models.loader import ModelLoader

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> bool:
    if not settings.API_KEY:
        return True
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events:
    - Startup: Load and warm up ML models
    - Shutdown: Clean up resources
    """
    # Startup: Load and warm up models
    logger.info("Starting %s...", settings.SERVICE_NAME)
    logger.info("Loading ML models...")
    try:
        ModelLoader.warmup()
        logger.info("Models loaded and warmed up successfully")
    except FileNotFoundError as e:
        logger.warning("Model loading failed: %s", e)
        logger.warning("Service starting without models - endpoints may fail")
    
    yield
    
    # Shutdown: Clean up
    logger.info("Shutting down %s...", settings.SERVICE_NAME)
    ModelLoader.clear()


def _get_cors_origins() -> list:
    if settings.CORS_ORIGINS:
        return [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    if settings.DEBUG:
        return ["*"]
    return ["http://localhost:8000"]


app = FastAPI(
    title="FaceLogix Face Recognition Service",
    description=(
        "Face detection, embedding generation, and liveness detection API. "
        "Provides endpoints for processing face images using RetinaFace "
        "detection and ArcFace embedding generation."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router with API key dependency
app.include_router(
    api_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_api_key)]
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.
    
    Returns service health status and model loading state.
    """
    models_loaded = (
        "detector" in ModelLoader._instances and
        "embedder" in ModelLoader._instances
    )
    
    return {
        "status": "healthy",
        "service": settings.SERVICE_NAME,
        "models_loaded": models_loaded
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint with service information.
    """
    return {
        "service": settings.SERVICE_NAME,
        "version": "1.0.0",
        "docs": "/api/docs"
    }
