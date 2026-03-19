"""
Debug script for verifying RAG retrieval across Qdrant collections.
"""

import asyncio
import logging

from llama_index.core import Settings, VectorStoreIndex
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from src.core.config import settings

logging.basicConfig(level=logging.INFO)


async def debug_retrieval() -> None:
    """Retrieve and print top-scoring nodes from each configured Qdrant collection."""
    Settings.embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    collections = ["pojehat_obd_ecu_v1", "pojehat_hybrid_v1"]

    query = "P0300 cylinder misfire 2010 Honda Civic"

    for coll in collections:
        print(f"\n--- Searching {coll} ---")
        try:
            is_hybrid = coll == "pojehat_obd_ecu_v1"
            vector_store = QdrantVectorStore(
                aclient=client,
                collection_name=coll,
                vector_name="text-dense" if is_hybrid else "default",
                sparse_vector_name="text-sparse" if is_hybrid else None,
                enable_hybrid=is_hybrid,
            )
            idx = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=Settings.embed_model,
            )
            retriever = idx.as_retriever(similarity_top_k=3)
            nodes: list[NodeWithScore] = await retriever.aretrieve(query)
            for i, n in enumerate(nodes):
                print(f"[{i}] Score: {n.score} | Content: {n.text[:200]}...")
        except (RuntimeError, ValueError, UnexpectedResponse) as e:
            print(f"Error querying {coll}: {e}")


if __name__ == "__main__":
    asyncio.run(debug_retrieval())
