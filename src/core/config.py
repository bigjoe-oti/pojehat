"""
Global configuration settings for the Pojehat backend.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings powered by Pydantic BaseSettings.
    """

    # API Keys
    OPENROUTER_API_KEY: str
    JINA_API_KEY: str | None = None

    # API Config
    API_V1_STR: str = "/api/v1"

    # Qdrant Config
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "pojehat_docs"

    # Model Config
    EMBED_MODEL: str = "text-embedding-3-small"
    LLM_MODEL_NAME: str = "x-ai/grok-4.1-fast"

    # Storage
    IMAGE_STORAGE_PATH: str = "/tmp/pojehat_images/"
    UPLOAD_DIR: str = "/tmp/pojehat_uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
