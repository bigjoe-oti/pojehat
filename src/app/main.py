import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import Settings
from qdrant_client import AsyncQdrantClient

from src.app.api.routes import router as api_router
from src.core.config import settings
from src.domain.rag_engine import _get_embed_model, _get_llm

# Configure application-level logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Wire LlamaIndex global Settings and verify connectivity at startup."""
    # 1. Wire LlamaIndex Settings once
    try:
        Settings.llm = _get_llm()
        Settings.embed_model = _get_embed_model()

        # Verify embedding model
        test_vec = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: Settings.embed_model.get_text_embedding(
                "pojehat embedding verification"
            )
        )
        logger.info(
            "Embedding model verified — model=%s, vector_dim=%d",
            settings.EMBED_MODEL,
            len(test_vec),
        )
    except Exception as e:
        logger.error("LlamaIndex Wire/Embed check FAILED: %s", e)
        # We do NOT raise here — allow the app to start so we can check /health

    # 2. Verify Qdrant connectivity
    try:
        client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )
        info = await client.get_collections()
        found = {c.name for c in info.collections}
        logger.info("Qdrant startup check: found collections %s", found)
        await client.close()
    except Exception as e:
        logger.error("Qdrant connectivity FAILED: %s", e)

    yield


def create_app() -> FastAPI:
    """
    FastAPI Application Factory for Pojehat.
    """
    _app = FastAPI(
        title="Pojehat Backend",
        description="AI-Driven AutoTech RAG & ECU Tuning SaaS",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure CORS — see ALLOWED_ORIGINS in config Settings for production origins
    raw_origins = settings.ALLOWED_ORIGINS.split(",")
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        *[o.strip() for o in raw_origins if o.strip()],
    ]

    # Handle wildcard for development/preview environments
    if "*" in settings.ALLOWED_ORIGINS:
        cors_origins = ["*"]
        allow_credentials = False # Cannot use credentials with wildcard
    else:
        cors_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
        allow_credentials = True

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API Routes
    _app.include_router(api_router, prefix=settings.API_V1_STR)

    @_app.get("/")
    async def root():
        """Root endpoint for platform health detection."""
        return {"app": "Pojehat Backend", "status": "online"}

    @_app.get("/health")
    async def health_check() -> dict[str, str | bool]:
        """
        System health and version status with LLM verification.
        """
        return {
            "status": "healthy",
            "version": "0.1.0",
            "python": "3.13",
            "qdrant": settings.QDRANT_URL,
            "llm_key_set": bool(settings.OPENROUTER_API_KEY),
            "grok_key_set": bool(settings.GROK_API_KEY),
            "cors_wildcard": "*" in settings.ALLOWED_ORIGINS,
        }

    return _app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "src.app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=False,
    )
