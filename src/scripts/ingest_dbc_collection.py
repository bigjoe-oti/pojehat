"""
Pojehat DBC Ingestion — Egyptian market CAN signal matrices.
Target: pojehat_obd_ecu_v1 (named vector: text-dense)

URLs verified live March 2026.
Note: opendbc/dbc/ path is active — do NOT change to can/dbc/.
"""
import asyncio
import hashlib
import logging
import re

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from llama_index.embeddings.openai import OpenAIEmbedding
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECTION_NAME = "pojehat_obd_ecu_v1"

_BASE = (
    "https://raw.githubusercontent.com/commaai/opendbc"
    "/master/opendbc/dbc/"
)

DBC_SOURCES = [
    {
        "url": _BASE + "hyundai_i30_2014.dbc",
        "vehicle": (
            "Hyundai Accent i30 2014 CAN DBC Signal Matrix "
            "Powertrain Wheel Speed Throttle Brake Engine RPM "
            "Egyptian Market Hyundai Platform"
        ),
    },
    {
        "url": _BASE + "bmw_e9x_e8x.dbc",
        "vehicle": (
            "BMW 3 Series 1 Series E90 E8x CAN DBC Signal "
            "Matrix Engine Transmission Steering ADAS "
            "Body Control Luxury Egyptian Market"
        ),
    },
    {
        "url": _BASE + "ford_cgea1_2_ptcan_2011.dbc",
        "vehicle": (
            "Ford Focus Fiesta CGEA1.2 Powertrain CAN DBC "
            "2011 Engine Transmission Throttle Speed "
            "Signal Matrix Egyptian Market"
        ),
    },
    {
        "url": _BASE + "gm_global_a_lowspeed.dbc",
        "vehicle": (
            "Chevrolet Cruze Aveo Optra GM Global A "
            "Low Speed CAN DBC Body Control BCM "
            "HVAC Lighting Signal Matrix Egyptian Market"
        ),
    },
    {
        "url": _BASE + "nissan_xterra_2011.dbc",
        "vehicle": (
            "Nissan Platform CAN DBC 2011 Powertrain "
            "Engine RPM Wheel Speed Throttle ABS "
            "Signal Matrix Nissan Sunny Family"
        ),
    },
    {
        "url": _BASE + "ford_lincoln_base_pt.dbc",
        "vehicle": (
            "Ford Lincoln Base Powertrain CAN DBC "
            "Engine Transmission Torque Speed "
            "Generic Ford Platform Signal Reference"
        ),
    },
]


def _chunk_dbc(content: str) -> list[str]:
    """
    Split DBC into BO_ message blocks including all
    SG_ signal definitions. Filters empty blocks.
    """
    pattern = r"(BO_ \d+ .*?(?=\nBO_ |\Z))"
    matches = re.findall(pattern, content, re.DOTALL)
    return [m.strip() for m in matches if m.strip()]


def _stable_id(url: str, index: int) -> int:
    """
    SHA-256 deterministic point ID.
    Stable across restarts — no duplicate accumulation.
    """
    raw = f"{url}::{index}".encode()
    return int(hashlib.sha256(raw).hexdigest()[:15], 16)


async def ingest_dbc(
    source: dict,
    client: AsyncQdrantClient,
    embed_model: OpenAIEmbedding,
) -> tuple[int, int]:
    url = source["url"]
    vehicle = source["vehicle"]

    logger.info("→ %s", vehicle[:70])

    # 1. Download
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            content = resp.text
    except Exception as e:
        logger.error("  ✗ Download failed: %s", str(e)[:100])
        return 0, 1

    # 2. Chunk
    chunks = _chunk_dbc(content)
    if not chunks:
        logger.warning(
            "  ⚠ No BO_ blocks found — skipping: %s",
            url.split("/")[-1]
        )
        return 0, 1

    logger.info("  %d message blocks", len(chunks))

    # 3. Embed + upsert in batches
    upserted = 0
    for i in range(0, len(chunks), 20):
        batch = chunks[i: i + 20]

        try:
            vectors = embed_model.get_text_embedding_batch(batch)
        except Exception as e:
            logger.error(
                "  ✗ Embedding batch %d failed: %s", i, str(e)[:80]
            )
            continue

        points = [
            models.PointStruct(
                id=_stable_id(url, i + j),
                # obd_ecu_v1 requires named vector "text-dense"
                # Never use this script for pojehat_hybrid_v1
                # which uses an unnamed default vector
                vector={"text-dense": vector},
                payload={
                    "text": chunk,
                    "vehicle_context": vehicle,
                    # "can_dbc" distinguishes CAN signal matrices
                    # from "protocol" (UDS/CAN tutorials) and
                    # "dtc_database" (fault code lists)
                    "domain_tag": "can_dbc",
                    "source": "opendbc_commaai_github",
                    "source_type": "technical_reference",
                    "file_name": url.split("/")[-1],
                },
            )
            for j, (chunk, vector) in enumerate(zip(batch, vectors))
        ]

        try:
            await client.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
            )
            upserted += len(points)
            logger.info(
                "  Indexed: %d/%d",
                min(i + 20, len(chunks)),
                len(chunks),
            )
        except Exception as e:
            logger.error(
                "  ✗ Upsert batch %d failed: %s", i, str(e)[:80]
            )

    logger.info(
        "  ✓ %s — %d points", vehicle[:45], upserted
    )
    return upserted, 0


async def main() -> None:
    # Safety assertion — collection name must be exact
    assert COLLECTION_NAME == "pojehat_obd_ecu_v1", (
        "Wrong collection target — aborting. "
        "DBC files must go to pojehat_obd_ecu_v1."
    )

    logger.info(
        "=== Pojehat DBC Ingestion | %s ===",
        COLLECTION_NAME
    )

    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )

    before = await client.get_collection(COLLECTION_NAME)
    logger.info("Before: %d points", before.points_count)

    total_ok, total_fail = 0, 0
    for source in DBC_SOURCES:
        ok, fail = await ingest_dbc(source, client, embed_model)
        total_ok += ok
        total_fail += fail

    after = await client.get_collection(COLLECTION_NAME)
    logger.info(
        "After: %d points (added: %d) | ✓ %d points  ✗ %d sources",
        after.points_count,
        after.points_count - before.points_count,
        total_ok,
        total_fail,
    )
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
