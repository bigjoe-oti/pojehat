"""
Global configuration settings for the Pojehat backend.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings powered by Pydantic BaseSettings.
    """

    # API Keys
    OPENROUTER_API_KEY: str = ""  # Used for LLMs and embeddings via OpenRouter
    GROK_API_KEY: str = ""        # Used for Grok LLM via OpenRouter
    JINA_API_KEY: str | None = None
    AUTO_DEV_API_KEY: str | None = None  # auto.dev VIN Decode + OEM Build Data

    # API Config
    API_V1_STR: str = "/api/v1"
    # Comma-separated allowed CORS origins — set in .env for production
    # e.g. ALLOWED_ORIGINS="https://app.pojehat.com,https://www.pojehat.com"
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Qdrant Config
    # Production: Qdrant Cloud (AWS us-east-1)
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # CarAPI — Vehicle engine, trim, spec data (free tier)
    # https://carapi.app/docs/ — JWT obtained at runtime via /api/auth/login
    CARAPI_TOKEN: str = ""
    CARAPI_SECRET: str = ""

    # Model Config
    # 1536 dims — matches live Qdrant collections.
    # DO NOT change to text-embedding-3-large without full re-ingestion.
    # Collections were built with 1536 dims.
    # Model Names (Default to GROK 4.1 for LLM + OpenAI text-embedding-3-small via OpenRouter fallback)
    LLM_MODEL_NAME: str = "x-ai/grok-4.1-fast"
    HYDE_MODEL_NAME: str = "x-ai/grok-4.1-fast"
    EMBED_MODEL: str = "openai/text-embedding-3-small"
    VISION_MODEL_NAME: str = "mistralai/pixtral-large-2411"
    # Multimodal vision model for technical image analysis (pinouts, waveforms).
    # Called via OPENROUTER_API_KEY — NOT GROK_API_KEY.
    # Uses /v1/chat/completions with image_url base64 content type.

    QDRANT_INGEST_COLLECTION: str = "pojehat_hybrid_v1"
    # Collection where uploaded PDFs and web content are indexed.
    # Must match one of the collections in _COLLECTION_CFG in rag_engine.py.
    # DO NOT set to "pojehat_docs" — that collection is never queried.

    # RAG Tuning
    # RRF score reference table (k=60, two collections):
    # rank-1 in both collections → score = 2/61  = 0.03279 (best possible)
    # rank-1 in one collection → score = 1/61 = 0.01639
    # rank-5 in one collection → score = 1/65 = 0.01538
    # Recommended default: 0.014 (captures useful context, excludes noise)
    RAG_SCORE_THRESHOLD: float = 0.014  # RRF-calibrated — NOT cosine similarity
    RAG_TOP_K: int = 15                # Nodes retrieved per collection
    RAG_FINAL_K: int = 20              # Max nodes passed to LLM after RRF
    KNOWLEDGE_AUDIT_TOP_K: int = 25    # Nodes per collection for corpus audits

    # Storage
    IMAGE_STORAGE_PATH: str = "/tmp/pojehat_images/"
    UPLOAD_DIR: str = "/tmp/pojehat_uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("RAG_SCORE_THRESHOLD")
    @classmethod
    def validate_rrf_threshold(cls, v: float) -> float:
        """Prevent accidental cosine-similarity values (>0.034)."""
        if v > 0.034:
            raise ValueError(
                f"RAG_SCORE_THRESHOLD={v} exceeds max RRF score (~0.033). "
                "This causes 100% gate failure. RRF range: ~0.013 to ~0.033."
            )
        return v


settings = Settings()

# ---------------------------------------------------------------------------
# Gap-aware retrieval domain tags (B1)
# These must match vehicle_context metadata values set during ingestion.
# Used by intent classification and retrieval routing to select correct top_k.
# ---------------------------------------------------------------------------

EGYPTIAN_MARKET_VEHICLES: list[str] = [
    "Nissan Sunny B17",
    "Nissan Sentra B17",
    "Toyota Corolla E210",
    "Chery Tiggo 7",
    "MG ZS",
    "MG ZS EV",
    "Peugeot 301",
    "Renault Logan",
    "Kia Cerato",
    "Kia Cerato BD",
    "Hyundai Accent",
    "Hyundai Accent RB",
    "Mitsubishi Lancer EX",
    "Skoda Octavia A7",
]

HV_SRS_KEYWORDS: list[str] = [
    "airbag", "srs", "air bag", "supplemental restraint",
    "high voltage", "hv battery", "hv system", "ev battery",
    "hybrid battery", "high-voltage", "كيس هواء", "وسادة هوائية",
]

PROTOCOL_KEYWORDS: list[str] = [
    "can bus", "can-bus", "uds", "doip", "lin bus",
    "iso 14229", "iso 15765", "k-line", "j1850",
    "unified diagnostic", "obd protocol",
]
