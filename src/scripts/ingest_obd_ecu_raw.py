import asyncio
import logging
import sys
import time
import uuid
from io import StringIO

import httpx
import pandas as pd
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("pojehat.obd_ecu_raw_ingester")

# Verified Sources
OBD_CSV_URL = "https://raw.githubusercontent.com/mytrile/obd-trouble-codes/master/obd-trouble-codes.csv"
OBD_JSON_URL = "https://gist.githubusercontent.com/wzr1337/3576402/raw/dtcmapping.json"

# Initialize Clients
client = QdrantClient(
    url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=60
)
oa_client = OpenAI(
    api_key=settings.OPENROUTER_API_KEY, base_url="https://openrouter.ai/api/v1"
)
COLLECTION_NAME = "pojehat_obd_ecu_v1"


def ensure_collection():
    """Ensure the hybrid collection exists with named vectors."""
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        logger.info("[*] Creating new collection: %s", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
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


def get_embedding(text: str):
    """Get embedding from OpenAI via OpenRouter."""
    response = oa_client.embeddings.create(model=settings.EMBED_MODEL, input=text)
    return response.data[0].embedding


def upsert_with_retry(points, retries=3):
    """Upsert points with simple retry logic."""
    for attempt in range(retries):
        try:
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            return
        except Exception as e:
            if attempt == retries - 1:
                raise e
            logger.warning(
                "[!] Upsert failed (attempt %d): %s. Retrying...", attempt + 1, e
            )
            time.sleep(2**attempt)


async def ingest_obd_csv():
    """Directly ingest OBD-II CSV data into Qdrant."""
    logger.info("[*] Fetching OBD-II CSV from: %s", OBD_CSV_URL)
    async with httpx.AsyncClient(follow_redirects=True) as h_client:
        response = await h_client.get(OBD_CSV_URL)
        response.raise_for_status()

    df = pd.read_csv(StringIO(response.text))
    logger.info("[+] Downloaded %d codes from CSV.", len(df))

    # Resumption logic
    try:
        current_count = client.get_collection(COLLECTION_NAME).points_count
        if current_count > 0:
            logger.info("[*] Resuming CSV ingestion from row %d", current_count)
            df = df.iloc[current_count:]
    except Exception:
        pass

    points = []
    for index, row in df.iterrows():
        code = str(row.get("code", "Unknown"))
        desc = str(row.get("description", ""))
        content = f"OBD-II Diagnostic Trouble Code: {code}\nDescription: {desc}"

        try:
            vector = get_embedding(content)
            point = models.PointStruct(
                id=str(uuid.uuid4()),
                vector={"text-dense": vector},
                payload={
                    "text": content,
                    "category": "OBD-II Diagnostic",
                    "code": code,
                    "source": "mytrile/obd-trouble-codes",
                    "type": "Technical Reference",
                },
            )
            points.append(point)
        except Exception as e:
            logger.error("[!] Failed to process row %d: %s", index, e)
            continue

        if len(points) >= 25:
            upsert_with_retry(points)
            logger.info("[+] Ingested OBD CSV batch up to row %d", index)
            points = []

    if points:
        upsert_with_retry(points)


async def ingest_obd_json():
    """Directly ingest OBD-II JSON data into Qdrant."""
    logger.info("[*] Fetching OBD-II JSON from: %s", OBD_JSON_URL)
    async with httpx.AsyncClient(follow_redirects=True) as h_client:
        response = await h_client.get(OBD_JSON_URL)
        response.raise_for_status()

    data = response.json()
    logger.info("[+] Downloaded %d codes from JSON Gist.", len(data))

    points = []
    count = 0
    for code, desc in data.items():
        content = f"OBD-II Diagnostic Trouble Code: {code}\nDescription: {desc}"
        try:
            vector = get_embedding(content)
            point = models.PointStruct(
                id=str(uuid.uuid4()),
                vector={"text-dense": vector},
                payload={
                    "text": content,
                    "category": "OBD-II Diagnostic",
                    "code": code,
                    "source": "wzr1337/dtcmapping",
                    "type": "Technical Reference",
                },
            )
            points.append(point)
            count += 1
        except Exception as e:
            logger.error("[!] Failed to process JSON item %s: %s", code, e)
            continue

        if len(points) >= 25:
            upsert_with_retry(points)
            logger.info("[+] Ingested OBD JSON batch up to item %d", count)
            points = []

    if points:
        upsert_with_retry(points)


async def main():
    try:
        ensure_collection()
        await ingest_obd_csv()
        await ingest_obd_json()
        logger.info("[SUCCESS] RAW OBD Ingestion complete.")
    except Exception as e:
        logger.error("[FATAL] Raw Ingestion failed: %s", e)


if __name__ == "__main__":
    asyncio.run(main())
