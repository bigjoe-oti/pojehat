"""
Verification script for the Pojehat embedding and vectorization pipeline.
"""

import asyncio

from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import AsyncQdrantClient

from src.core.config import settings


async def verify_pipeline() -> None:
    print("--- Pojehat Pipeline Verification ---")

    # 1. Verify Embedding Model Metadata
    print(f"[*] Initializing remote embedding model: {settings.EMBED_MODEL}...")
    try:
        embed_model = OpenAIEmbedding(
            model=settings.EMBED_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            api_base="https://openrouter.ai/api/v1",
        )
        # Just check if it can generate a dummy embedding
        test_embed = embed_model.get_text_embedding("Pojehat AutoTech")
        print(f"[+] Embedding model initialized. Vector dim: {len(test_embed)}")
    except (Exception, ConnectionError, RuntimeError) as e:
        print(f"[!] Embedding model failure (Details: {type(e).__name__}): {e}")
        return

    # 2. Verify Qdrant Cloud Connection
    print(f"[*] Connecting to Qdrant Cloud: {settings.QDRANT_URL}...")
    try:
        client = AsyncQdrantClient(
            url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY
        )
        collections = await client.get_collections()
        print(
            f"[+] Connected to Qdrant. Collections found: "
            f"{[c.name for c in collections.collections]}"
        )

        # Check if our specific collection exists
        exists = any(
            c.name == settings.QDRANT_COLLECTION_NAME for c in collections.collections
        )
        if exists:
            print(f"[+] Collection '{settings.QDRANT_COLLECTION_NAME}' exists.")
        else:
            print(
                f"[!] Collection '{settings.QDRANT_COLLECTION_NAME}' NOT found. "
                "You may need to create it."
            )

    except (Exception, ConnectionError, RuntimeError) as e:
        print(f"[!] Qdrant connection failure (Details: {type(e).__name__}): {e}")
        return

    print("--- Verification Complete ---")


if __name__ == "__main__":
    asyncio.run(verify_pipeline())
