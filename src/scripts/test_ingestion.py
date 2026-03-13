"""
CLI test script for verified Pojehat embedding and Qdrant ingestion.
"""

import asyncio

from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from src.core.config import settings


async def test_manual_ingestion() -> None:
    """
    Tests the embedding wiring and Qdrant connection directly.
    """
    print("[*] Initializing OpenAI Embedding (via OpenRouter)...")
    # Initialize OpenAI Embedding using OpenRouter
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    print(f"[*] Connecting to Qdrant... at {settings.QDRANT_URL}")
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    try:
        # 1. Ensure collection exists
        collections = await client.get_collections()
        exists = any(
            c.name == settings.QDRANT_COLLECTION_NAME for c in collections.collections
        )

        if not exists:
            print(f"[*] Creating collection '{settings.QDRANT_COLLECTION_NAME}'...")
            await client.create_collection(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=1536, distance=models.Distance.COSINE
                ),
            )

        # 2. Embed dummy text
        text = "This is a test document for the Pojehat Spark Plug diagnostic system."
        print("[*] Generating embedding...")
        embedding = embed_model.get_text_embedding(text)
        print("[+] Embedding generated.")

        # 3. Upsert into Qdrant
        print("[*] Pushing to Qdrant...")
        await client.upsert(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=1,
                    vector=embedding,
                    payload={"text": text, "source": "test_script"},
                )
            ],
        )
        print("[+] Successfully pushed to Qdrant.")

    except Exception as e:
        print(f"[!] Pipeline failure: {str(e)}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_manual_ingestion())
