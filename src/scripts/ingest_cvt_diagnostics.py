import asyncio
import logging
import sys

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from src.core.config import settings
from src.services.web_ingester import WebIngester

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Very specific, highly technical CVT & Transmission links
CVT_SOURCES = [
    # NHTSA Technical Service Bulletins for CVT
    "https://static.nhtsa.gov/odi/tsbs/2021/MC-10199252-0001.pdf", # Nissan CVT Judder
    "https://static.nhtsa.gov/odi/tsbs/2018/MC-10142918-9999.pdf", # Honda CVT Failure
    "https://static.nhtsa.gov/odi/tsbs/2016/MC-10106899-9340.pdf", # Subaru TR690 CVT

    # Generic Transmission/Guided Diagnostics (Educational / Fleet)
    "https://www.sae.org/publications/technical-papers/content/2006-01-0975/", # SAE CVT Performance
    "https://atracom.com/wp-content/uploads/2019/07/2019_Seminar_Manual.pdf", # ATRA Master CVT Diagnostics (Huge)

    # Lamp Malfunctions / Electrical
    "https://static.nhtsa.gov/odi/tsbs/2019/MC-10168759-0001.pdf", # Audi/VAG LED Matrix Lamp Malfunction
    "https://static.nhtsa.gov/odi/tsbs/2018/MC-10148892-9999.pdf", # BMW Lighting & LCM failures
]


async def get_index() -> VectorStoreIndex:
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    collection_name = "pojehat_hybrid_v1"

    try:
        await client.get_collection(collection_name)
    except Exception:
        logger.info(f"Collection {collection_name} not found. Creating.")
        await client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "text-dense": models.VectorParams(
                    size=1536,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "text-sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=False)
                )
            },
        )

    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        aclient=client,
        enable_hybrid=True,
        batch_size=20,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )
    return index


async def main():
    try:
        await get_index()  # initialises Qdrant index (side-effect)
        ingester = WebIngester()

        logger.info("Initializing CVT and Guided Diagnostic Deep-Web Scraping...")

        for url in CVT_SOURCES:
            logger.info(f"Scraping {url}...")
            try:
                # process_url automatically handles downloading, parsing, and vector ingestion natively
                await ingester.process_url(url, vehicle_context="CVT_And_Lamp_Diagnostics")
            except Exception as e:
                 logger.error(f"❌ Error scraping {url}: {e}")

        logger.info("✅ CVT and Advanced Diagnostic Ingestion Complete!")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
