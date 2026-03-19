"""
Targeted ingestion script for Chery DTC codes from procarmanuals.com.

Strategy:
  - Parse the full DTC list from the source URL via httpx
  - Group codes into logical system-category chunks
  - Upsert each chunk into pojehat_hybrid_v1 with rich Qdrant payload metadata:
      make, domain_tag, source_type, dtc_range, system_category,
      vehicle_context, source, title
  - Uses the same embedding model singleton as the rest of the pipeline
  - Deduplication: checks source URL + make before upserting
"""

import asyncio
import hashlib
import logging
import re
import uuid
from dataclasses import dataclass

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
)

from src.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

SOURCE_URL = "https://procarmanuals.com/chery-diagnostic-trouble-codes/"
COLLECTION = "pojehat_hybrid_v1"
MAKE = "Chery"
VEHICLE_CONTEXT = "Chery — All Models (Egyptian market)"
DOMAIN_TAG = "fault_diagnosis"

# Category boundaries — keyed on first DTC code in the range
DTC_CATEGORIES: list[tuple[str, str]] = [
    ("P0100", "Air Flow / MAP / MAF Sensors"),
    ("P0110", "Intake Air Temperature Sensors"),
    ("P0115", "Engine Coolant Temperature Sensors"),
    ("P0120", "Throttle Position Sensors"),
    ("P0130", "Oxygen / Lambda Sensors"),
    ("P0170", "Fuel Mixture / Composition"),
    ("P0180", "Fuel Temperature Sensors"),
    ("P0195", "Oil Temperature Sensors"),
    ("P0200", "Fuel Injectors"),
    ("P0230", "Fuel Pump & Turbocharger"),
    ("P0250", "Injector Pump Sensors"),
    ("P0300", "Misfire Detection"),
    ("P0320", "Ignition / Distributor"),
    ("P0325", "Knock Sensors"),
    ("P0335", "Crankshaft / Camshaft Position Sensors"),
    ("P0350", "Ignition Coils"),
    ("P0370", "Timer Signals & Glow Plugs"),
    ("P0380", "EGR — Exhaust Gas Recirculation"),
    ("P0400", "EGR System (Detailed)"),
    ("P0410", "Secondary Air Injection"),
    ("P0420", "Catalytic Converter"),
    ("P0440", "EVAP — Fuel Vapor System"),
    ("P0460", "Fuel Level / Purge Sensors"),
    ("P0470", "Exhaust Pressure Sensors"),
    ("P0480", "Cooling Fans"),
    ("P0500", "Vehicle Speed / Idle Control"),
    ("P0520", "Oil Pressure Sensor"),
    ("P0530", "A/C & Power Steering Pressure"),
    ("P0560", "System Voltage & Cruise Control"),
    ("P0600", "ECU / PCM Communication & Memory"),
    ("P0620", "Generator / Charging System"),
    ("P0700", "Transmission Control System"),
    ("P0750", "Transmission Solenoids"),
    ("P0780", "Transmission Switches"),
    ("P0801", "Reverse Inhibit / Solenoid Switches"),
    ("P1100", "Manufacture-Specific: Sensors (P1xxx)"),
    ("P1330", "Manufacture-Specific: Ignition / Crankshaft"),
    ("P1380", "Manufacture-Specific: Communication Faults"),
    ("P1400", "Manufacture-Specific: EGR / EVAP"),
    ("P1550", "Manufacture-Specific: Cruise / Fuel System"),
    ("P1620", "Manufacture-Specific: Electrical/System"),
]


# ── Data model ─────────────────────────────────────────────────────────────────


@dataclass
class DtcEntry:
    code: str
    description: str


@dataclass
class DtcChunk:
    category: str
    codes: list[DtcEntry]

    @property
    def dtc_range(self) -> str:
        if not self.codes:
            return ""
        return f"{self.codes[0].code}–{self.codes[-1].code}"

    @property
    def text(self) -> str:
        header = (
            f"# Chery DTC Reference — {self.category}\n\n"
            f"Make: {MAKE}\n"
            f"DTC Range: {self.dtc_range}\n"
            f"Vehicle Context: {VEHICLE_CONTEXT}\n\n"
            f"## Fault Codes\n\n"
        )
        rows = "\n".join(
            f"- **{e.code}** — {e.description}" for e in self.codes
        )
        return header + rows


# ── Parser ─────────────────────────────────────────────────────────────────────


def _parse_dtc_text(raw: str) -> list[DtcEntry]:
    """
    Parse the raw DTC text block (space-separated code + description pairs)
    into structured DtcEntry objects.
    """
    # Match: P followed by 4 digits, then the rest until the next P-code
    pattern = re.compile(r"(P\d{4})\s+([^P]+?)(?=P\d{4}|$)")
    entries: list[DtcEntry] = []
    for match in pattern.finditer(raw):
        code = match.group(1).strip()
        desc = match.group(2).strip().rstrip(".")
        if desc:
            entries.append(DtcEntry(code=code, description=desc))
    return entries


def _categorise_entries(entries: list[DtcEntry]) -> list[DtcChunk]:
    """
    Distribute DTC entries into system-category chunks based on code ranges.
    """
    # Build sorted boundary list
    boundaries = [(code, label) for code, label in DTC_CATEGORIES]
    boundaries.sort(key=lambda x: x[0])

    chunks: list[DtcChunk] = []

    for i, (start_code, label) in enumerate(boundaries):
        end_code = boundaries[i + 1][0] if i + 1 < len(boundaries) else "P9999"
        bucket: list[DtcEntry] = [
            e for e in entries
            if start_code <= e.code < end_code
        ]
        if bucket:
            chunks.append(DtcChunk(category=label, codes=bucket))

    return chunks


# ── Embedding ──────────────────────────────────────────────────────────────────


async def _embed(texts: list[str]) -> list[list[float]]:
    """
    Call the OpenRouter embedding endpoint (same model used by rag_engine).
    """
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://pojehat.ai",
        "X-Title": "Pojehat DTC Ingestion",
    }
    payload = {
        "model": settings.EMBED_MODEL,
        "input": texts,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/embeddings",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
    return [item["embedding"] for item in data["data"]]


# ── Deduplication ──────────────────────────────────────────────────────────────


async def _already_ingested(qdrant: AsyncQdrantClient) -> bool:
    """Return True if Chery DTC data from this URL is already in the collection."""
    try:
        result = await qdrant.count(
            collection_name=COLLECTION,
            count_filter=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(value=SOURCE_URL),
                    ),
                    FieldCondition(
                        key="make",
                        match=MatchValue(value=MAKE),
                    ),
                ]
            ),
            exact=False,
        )
        return result.count > 0
    except Exception as e:
        logger.warning("Dedup check failed: %s", e)
        return False


# ── Main ───────────────────────────────────────────────────────────────────────


async def main() -> None:
    logger.info("=== Chery DTC Ingestion — Starting ===")

    # 1. Fetch page content
    logger.info("Fetching: %s", SOURCE_URL)
    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        },
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        response = await client.get(SOURCE_URL)
        response.raise_for_status()
        raw_html = response.text

    # 2. Strip HTML tags to get pure DTC text
    raw_text = re.sub(r"<[^>]+>", " ", raw_html)
    raw_text = re.sub(r"\s+", " ", raw_text).strip()

    # 3. Parse DTC entries
    entries = _parse_dtc_text(raw_text)
    logger.info("Parsed %d DTC entries.", len(entries))
    if not entries:
        logger.error("No DTC entries parsed — check HTML structure.")
        return

    # 4. Group into system-category chunks
    chunks = _categorise_entries(entries)
    logger.info("Organised into %d system-category chunks.", len(chunks))

    # 5. Connect to Qdrant
    qdrant = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )

    # 6. Deduplication check
    if await _already_ingested(qdrant):
        logger.info(
            "Chery DTC data already present in %s — skipping.", COLLECTION
        )
        return

    # 7. Embed + upsert chunk-by-chunk
    total_upserted = 0
    for chunk in chunks:
        logger.info(
            "[%s] Embedding %d codes (%s)...",
            chunk.category,
            len(chunk.codes),
            chunk.dtc_range,
        )
        try:
            vectors = await _embed([chunk.text])
            vector = vectors[0]

            # Deterministic UUID from source + category for idempotency
            point_id = str(
                uuid.UUID(
                    hashlib.md5(
                        f"{SOURCE_URL}::{chunk.category}".encode()
                    ).hexdigest()
                )
            )

            point = PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    # Retrieval metadata
                    "text": chunk.text,
                    "source": SOURCE_URL,
                    "title": f"Chery DTC — {chunk.category}",
                    # Rich domain metadata
                    "make": MAKE,
                    "vehicle_context": VEHICLE_CONTEXT,
                    "domain_tag": DOMAIN_TAG,
                    "source_type": "dtc_reference",
                    "dtc_range": chunk.dtc_range,
                    "system_category": chunk.category,
                    "dtc_count": len(chunk.codes),
                    # Individual DTC codes as searchable list
                    "dtc_codes": [e.code for e in chunk.codes],
                },
            )

            await qdrant.upsert(
                collection_name=COLLECTION,
                points=[point],
            )
            total_upserted += 1
            logger.info(
                "[+] Upserted: %s (%s — %d codes)",
                chunk.category,
                chunk.dtc_range,
                len(chunk.codes),
            )

        except Exception as e:
            logger.error(
                "[!] Failed chunk '%s': %s", chunk.category, e
            )

    await qdrant.close()
    logger.info(
        "=== Done. Upserted %d/%d chunks into %s ===",
        total_upserted,
        len(chunks),
        COLLECTION,
    )


if __name__ == "__main__":
    asyncio.run(main())
