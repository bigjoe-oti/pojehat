"""
CarAPI Ingestion Script — Lockstep Ingestion (Instant-Save)
==========================================================
Fetches vehicle data from carapi.app and ingests into Qdrant page-by-page.
This ensures that if a rate limit or crash occurs, we keep what was done.

Redesign:
- Instead of Fetch-All then Index, it does Fetch-Batch -> Join -> Index.
- Uses src/data/carapi_cache/ to remember which pages have been successfully indexed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx
from llama_index.core import Document

from src.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

MENA_MAKES: list[str] = [
    "Nissan", "Toyota", "Hyundai", "Kia", "Renault",
    "Peugeot", "Citroen", "Mitsubishi", "Chevrolet", "Honda",
    "Suzuki", "Ford", "Volkswagen", "BMW", "Mercedes-Benz",
    "Fiat", "Mazda", "Subaru", "Isuzu", "Land Rover",
    "Jaguar", "Porsche", "Audi", "Skoda", "Geely",
]

CARAPI_BASE = "https://carapi.app/api"
YEAR_MIN = 2005
PAGE_LIMIT = 100
CACHE_DIR = Path("/Users/OTI_1/Desktop/pojehat/src/data/carapi_cache")


async def _get_jwt(client: httpx.AsyncClient) -> str:
    if not settings.CARAPI_TOKEN or not settings.CARAPI_SECRET:
        logger.error("CARAPI_TOKEN/SECRET missing in env.")
        sys.exit(1)
    resp = await client.post(
        f"{CARAPI_BASE}/auth/login",
        json={"api_token": settings.CARAPI_TOKEN, "api_secret": settings.CARAPI_SECRET},
    )
    resp.raise_for_status()
    return resp.text.strip()


def _is_page_indexed(endpoint: str, page: int) -> bool:
    marker = CACHE_DIR / f"{endpoint.replace('/', '_')}_page_{page}.done"
    return marker.exists()


def _mark_page_indexed(endpoint: str, page: int) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    marker = CACHE_DIR / f"{endpoint.replace('/', '_')}_page_{page}.done"
    marker.touch()


async def _fetch_page(
    client: httpx.AsyncClient, jwt: str, endpoint: str, page: int, filters: str
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {jwt}", "accept": "application/json"}
    params = {"page": page, "limit": PAGE_LIMIT, "json": filters}
    
    while True:
        resp = await client.get(f"{CARAPI_BASE}/{endpoint}", headers=headers, params=params)
        if resp.status_code == 429:
            logger.warning("Rate-limited. Sleeping 60s...")
            await asyncio.sleep(60)
            continue
        resp.raise_for_status()
        return resp.json()


def _build_doc(trim: dict, engine: dict, body: dict, mileage: dict) -> Document:
    # Minimal fields for joining
    make = trim.get("make", "")
    model = trim.get("model", "")
    year = trim.get("year", "")
    trim_name = trim.get("trim", "")

    text = f"""# {year} {make} {model} — {trim_name}
## Engine
- HP: {engine.get('horsepower_hp', 'N/A')} | Torque: {engine.get('torque_ft_lbs', 'N/A')}
- Type: {engine.get('engine_type', 'N/A')} | Disp: {engine.get('size', 'N/A')}L
## Body
- Style: {body.get('type', 'N/A')} | Curb: {body.get('curb_weight', 'N/A')} lbs
## Economy
- Tank: {mileage.get('fuel_tank_capacity', 'N/A')} gal | MPG: {mileage.get('combined_mpg', 'N/A')}
"""
    return Document(
        text=text,
        metadata={
            "source": "carapi.app",
            "make": make,
            "model": model,
            "year": str(year),
            "trim": trim_name,
            "collection": "pojehat_hybrid_v1",
        },
        id_=f"carapi_{make}_{model}_{year}_{trim_name}".replace(" ", "_").lower(),
    )


async def run_ingestion(makes: list[str], dry_run: bool = False):
    from src.domain.pdf_parser import index_documents
    loop = asyncio.get_running_loop()

    filters = json.dumps([
        {"field": "make", "op": "in", "val": makes},
        {"field": "year", "op": ">=", "val": YEAR_MIN},
    ])

    async with httpx.AsyncClient() as client:
        jwt = await _get_jwt(client)
        
        # Get total pages from trims endpoint
        init_data = await _fetch_page(client, jwt, "trims/v2", 1, filters)
        total_pages = int(init_data.get("collection", {}).get("pages", 1))
        
        logger.info("Found %d pages across all endpoints.", total_pages)

        for page in range(1, total_pages + 1):
            if _is_page_indexed("global_batch", page):
                logger.info("Page %d already indexed. Skipping.", page)
                continue

            logger.info("Processing Page %d/%d...", page, total_pages)
            
            # Fetch all 4 parts for this page batch
            trims_data = await _fetch_page(client, jwt, "trims/v2", page, filters)
            engines_data = await _fetch_page(client, jwt, "engines/v2", page, filters)
            bodies_data = await _fetch_page(client, jwt, "bodies/v2", page, filters)
            mileages_data = await _fetch_page(client, jwt, "mileages/v2", page, filters)

            # Index by trim_id for fast join
            e_idx = {r["trim_id"]: r for r in engines_data["data"] if "trim_id" in r}
            b_idx = {r["trim_id"]: r for r in bodies_data["data"] if "trim_id" in r}
            m_idx = {r["trim_id"]: r for r in mileages_data["data"] if "trim_id" in r}

            batch_docs: list[Document] = []
            for trim in trims_data["data"]:
                tid = trim.get("id")
                doc = _build_doc(trim, e_idx.get(tid, {}), b_idx.get(tid, {}), m_idx.get(tid, {}))
                batch_docs.append(doc)

            if not dry_run:
                # Instant save to Qdrant
                await loop.run_in_executor(None, index_documents, batch_docs)
                _mark_page_indexed("global_batch", page)
                logger.info("  Page %d ingested successfully (%d docs)", page, len(batch_docs))
            else:
                logger.info("  Page %d dry run (not saved)", page)

            await asyncio.sleep(0.5)

    logger.info("✅ Lockstep ingestion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(run_ingestion(makes=MENA_MAKES, dry_run=args.dry_run))
