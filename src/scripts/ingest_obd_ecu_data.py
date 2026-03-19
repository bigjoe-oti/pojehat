"""Ingestion script for OBD-II ECU data.

Deterministic doc_id via SHA-256 ensures re-ingestion upserts rather than duplicates.
"""

import asyncio
import hashlib
import logging
import sys
from io import StringIO

import httpx
import pandas as pd
import tiktoken
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.core.config import settings

# Force LlamaIndex to use tiktoken for tokenization to avoid transformers dependency
Settings.tokenizer = tiktoken.encoding_for_model("text-embedding-3-small").encode
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("pojehat.obd_ecu_ingester")

# Verified Sources
OBD_CSV_URL = "https://raw.githubusercontent.com/mytrile/obd-trouble-codes/master/obd-trouble-codes.csv"
OBD_JSON_URL = "https://gist.githubusercontent.com/wzr1337/3576402/raw/dtcmapping.json"


async def get_index() -> VectorStoreIndex:
    """Initialize the RAG index with a fresh, correctly-named hybrid schema."""
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    # Sync Client for LlamaIndex stability during point-upload
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = "pojehat_obd_ecu_v1"

    # Create collection if missing (Sync)
    try:
        client.get_collection(collection_name)
    except Exception:
        logger.info("[*] Creating new collection: %s", collection_name)
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "text-dense": models.VectorParams(
                    size=1536, distance=models.Distance.COSINE
                )
            },
            sparse_vectors_config={
                "text-sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=True)
                )
            },
        )

    # Initialize the vector store with explicit named vector support
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        vector_name="text-dense",
        sparse_vector_name="text-sparse",
        enable_hybrid=True,
    )

    # Use SentenceSplitter as a standalone transformation to avoid TokenTextSplitter
    # (which needs transformers)
    splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
        storage_context=storage_context,
        transformations=[splitter],  # Pass explicitly to override defaults
    )


async def ingest_obd_csv():
    """Download and ingest the Mytrile OBD-II CSV dataset."""
    logger.info("[*] Fetching OBD-II CSV from: %s", OBD_CSV_URL)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(OBD_CSV_URL)
        response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))
    logger.info("[+] Downloaded %d codes from CSV.", len(df))

    documents: list[Document] = []
    for _, row in df.iterrows():
        code = str(row.get("code", "Unknown"))
        desc = str(row.get("description", ""))
        content = f"OBD-II Diagnostic Trouble Code: {code}\nDescription: {desc}"

        # Deterministic doc_id — upserts on re-run, zero duplicates
        doc_id = hashlib.sha256(f"obd_csv|{code}".encode()).hexdigest()
        doc = Document(
            text=content,
            metadata={
                "category": "OBD-II Diagnostic",
                "code": code,
                "source": "mytrile/obd-trouble-codes",
                "type": "Technical Reference",
            },
            doc_id=doc_id,
        )
        documents.append(doc)

    index = await get_index()
    for i in range(0, len(documents), 50):
        batch = documents[i : i + 50]
        await asyncio.to_thread(index.refresh_ref_docs, batch)
        logger.info("[+] Ingested OBD CSV batch %d-%d", i, i + len(batch))


async def ingest_obd_json():
    """Download and ingest the wzr1337 OBD-II JSON dataset."""
    logger.info("[*] Fetching OBD-II JSON from: %s", OBD_JSON_URL)
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(OBD_JSON_URL)
        response.raise_for_status()

    data = response.json()
    logger.info("[+] Downloaded %d codes from JSON Gist.", len(data))

    documents: list[Document] = []
    for code, desc in data.items():
        content = f"OBD-II Diagnostic Trouble Code: {code}\nDescription: {desc}"
        # Deterministic doc_id — upserts on re-run, zero duplicates
        doc_id = hashlib.sha256(f"obd_json|{code}".encode()).hexdigest()
        doc = Document(
            text=content,
            metadata={
                "category": "OBD-II Diagnostic",
                "code": code,
                "source": "wzr1337/dtcmapping",
                "type": "Technical Reference",
            },
            doc_id=doc_id,
        )
        documents.append(doc)

    index = await get_index()
    for i in range(0, len(documents), 50):
        batch = documents[i : i + 50]
        await asyncio.to_thread(index.refresh_ref_docs, batch)
        logger.info("[+] Ingested OBD JSON batch %d-%d", i, i + len(batch))


async def main():
    """Execute the ingestion of OBD-II datasets."""
    try:
        await ingest_obd_csv()
        await ingest_obd_json()
        logger.info("[SUCCESS] OBD Technical data ingestion complete.")
    except Exception as e:
        logger.error("[FATAL] Ingestion failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
