import asyncio
import logging

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from src.core.config import settings


async def init_indices():
    logging.basicConfig(level=logging.INFO)
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    collections = ["pojehat_hybrid_v1", "pojehat_obd_ecu_v1"]

    for coll in collections:
        print(f"[*] Ensuring 'source' keyword index for collection: {coll}")
        try:
            await client.create_payload_index(
                collection_name=coll,
                field_name="source",
                field_schema=models.PayloadSchemaType.KEYWORD,
            )
            print(f"✅ Index created/verified for {coll}")
        except Exception as e:
            print(f"[-] Error or already exists for {coll}: {e}")

if __name__ == "__main__":
    asyncio.run(init_indices())
