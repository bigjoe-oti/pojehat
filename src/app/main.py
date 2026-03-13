"""
Main entry point for the Pojehat FastAPI application.
"""

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.app.api.routes import router as api_router
from src.core.config import settings


def create_app() -> FastAPI:
    """
    FastAPI Application Factory for Pojehat.
    """
    _app = FastAPI(
        title="Pojehat Backend",
        description="AI-Driven AutoTech RAG & ECU Tuning SaaS",
        version="0.1.0",
    )

    # Configure CORS
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Open to all origins for now
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API Routes
    _app.include_router(api_router, prefix=settings.API_V1_STR)

    @_app.get("/health")
    async def health_check() -> dict[str, str]:
        """
        System health and version status.
        """
        return {
            "status": "healthy",
            "version": "0.1.0",
            "python": "3.13",
            "qdrant": settings.QDRANT_URL,
        }

    return _app


app = create_app()

if __name__ == "__main__":
    uvicorn.run("src.app.main:app", host="0.0.0.0", port=8000, reload=True)
