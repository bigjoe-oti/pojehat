"""
NHTSA Recalls & Complaints Ingestion Script
============================================
Fetches zero-auth, free data from NHTSA's public API:
  - Recalls   : https://api.nhtsa.dot.gov/recalls/recallsByVehicle
  - Complaints: https://api.nhtsa.dot.gov/complaints/complaintsByVehicle

For each MENA-priority make/model/year combination, pulls all recall
campaigns and consumer complaint clusters and vectorises them into
pojehat_hybrid_v1 — giving the RAG engine real-world failure pattern
data to ground its OBD and diagnostic responses.

No API key required. Polite rate pacing (0.3s between requests).

Usage:
    python -m src.scripts.ingest_nhtsa [--dry-run] [--years 2010 2024]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any

import httpx
from llama_index.core import Document

from src.domain.pdf_parser import index_documents

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

NHTSA_BASE = "https://api.nhtsa.dot.gov"

# ---------------------------------------------------------------------------
# MENA Vehicle Matrix — make → list of common model names
# Expand as needed. These are the most common vehicles in EG/SA/AE/MA markets.
# ---------------------------------------------------------------------------
MENA_VEHICLES: dict[str, list[str]] = {
    "NISSAN": [
        "SUNNY", "SENTRA", "ALTIMA", "QASHQAI", "X-TRAIL",
        "MAXIMA", "NAVARA", "PATROL", "TIIDA",
    ],
    "TOYOTA": [
        "COROLLA", "CAMRY", "YARIS", "RAV4", "HILUX",
        "FORTUNER", "LAND CRUISER", "PRADO",
    ],
    "HYUNDAI": [
        "ACCENT", "ELANTRA", "SONATA", "TUCSON", "SANTA FE", "VERNA",
    ],
    "KIA": [
        "CERATO", "SPORTAGE", "SORENTO", "PICANTO", "OPTIMA", "STINGER",
    ],
    "MITSUBISHI": [
        "LANCER", "GALANT", "OUTLANDER", "ECLIPSE CROSS", "PAJERO",
    ],
    "RENAULT": [
        "LOGAN", "MEGANE", "FLUENCE", "DUSTER", "KOLEOS", "CLIO",
    ],
    "CHEVROLET": [
        "CRUZE", "AVEO", "SONIC", "OPTRA", "CAPTIVA", "TRAILBLAZER",
    ],
    "HONDA": [
        "CIVIC", "ACCORD", "CR-V", "HR-V", "FIT", "CITY",
    ],
    "VOLKSWAGEN": ["GOLF", "PASSAT", "TIGUAN", "POLO", "JETTA"],
    "BMW":        ["3 SERIES", "5 SERIES", "X3", "X5", "1 SERIES"],
    "MERCEDES-BENZ": ["C-CLASS", "E-CLASS", "GLC", "A-CLASS"],
    "FORD":       ["FOCUS", "FUSION", "ESCAPE", "F-150", "FIESTA"],
    "PEUGEOT":    ["301", "308", "2008", "3008", "5008"],
    "SUZUKI":     ["SWIFT", "VITARA", "JIMNY", "CIAZ"],
    "MAZDA":      ["MAZDA3", "MAZDA6", "CX-5", "CX-30"],
    "FIAT":       ["TIPO", "500", "BRAVO"],
    "SUBARU":     ["OUTBACK", "FORESTER", "IMPREZA", "XV"],
    "LAND ROVER": ["DISCOVERY", "RANGE ROVER", "DEFENDER", "EVOQUE"],
}

YEAR_RANGE = range(2010, 2025)   # 15 years of MENA-relevant data


# ---------------------------------------------------------------------------
# Fetch helpers
# ---------------------------------------------------------------------------

async def _fetch_recalls(
    client: httpx.AsyncClient, make: str, model: str, year: int
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{NHTSA_BASE}/recalls/recallsByVehicle",
        params={"make": make, "model": model, "modelYear": year},
        timeout=15.0,
    )
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []


async def _fetch_complaints(
    client: httpx.AsyncClient, make: str, model: str, year: int
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{NHTSA_BASE}/complaints/complaintsByVehicle",
        params={"make": make, "model": model, "modelYear": year},
        timeout=15.0,
    )
    if resp.status_code == 200:
        return resp.json().get("results", [])
    return []


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------

def _build_recall_doc(make: str, model: str, year: int,
                       recall: dict[str, Any]) -> Document:
    campaign  = recall.get("NHTSACampaignNumber", "N/A")
    comp      = recall.get("Component", "N/A")
    summary   = recall.get("Summary", "")
    conq      = recall.get("Consequence", "")
    remedy    = recall.get("Remedy", "")
    mfr_notes = recall.get("Notes", "")
    report_dt = recall.get("ReportReceivedDate", "N/A")

    text = f"""\
# NHTSA Safety Recall — {year} {make} {model}

**Campaign Number:** {campaign}
**Report Date:** {report_dt}
**Component / System:** {comp}

## Summary
{summary}

## Consequence
{conq}

## Remedy / Fix
{remedy}

## Manufacturer Notes
{mfr_notes}
"""
    return Document(
        text=text,
        metadata={
            "source": "NHTSA_recalls",
            "intent": "DIAGNOSTIC",
            "make": make.title(),
            "model": model.title(),
            "year": str(year),
            "campaign": campaign,
            "component": comp,
            "collection": "pojehat_hybrid_v1",
        },
        id_=f"nhtsa_recall_{campaign}_{make}_{model}_{year}".replace(" ", "_").lower(),
    )


def _build_complaint_doc(make: str, model: str, year: int,
                          complaints: list[dict[str, Any]]) -> Document | None:
    if not complaints:
        return None

    # Aggregate complaint cluster into a single document
    comp_part = complaints[0].get("Component", "Unknown System")
    total     = len(complaints)
    lines: list[str] = []

    for c in complaints[:15]:   # Cap at 15 to keep doc size reasonable
        desc     = c.get("CDTRText", "").strip()
        mileage  = c.get("Mileage", "N/A")
        crash    = c.get("Crash", False)
        fire     = c.get("Fire", False)
        dt       = c.get("DateOfIncident", "")
        flags    = []
        if crash:
            flags.append("CRASH")
        if fire:
            flags.append("FIRE")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"- ({dt}, {mileage} mi{flag_str}): {desc[:300]}"
        )

    text = f"""\
# NHTSA Consumer Complaints — {year} {make} {model}
**System / Component:** {comp_part}
**Total Complaints Reported:** {total}

## Complaint Descriptions (sample of up to 15)
{chr(10).join(lines)}
"""
    return Document(
        text=text,
        metadata={
            "source": "NHTSA_complaints",
            "intent": "DIAGNOSTIC",
            "make": make.title(),
            "model": model.title(),
            "year": str(year),
            "component": comp_part,
            "collection": "pojehat_hybrid_v1",
        },
        id_=(
            f"nhtsa_complaint_{make}_{model}_{year}_{comp_part}"
            .replace(" ", "_").lower()[:120]
        ),
    )


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_ingestion(year_range: range, dry_run: bool = False) -> None:
    logger.info("=== NHTSA Recalls + Complaints Ingestion ===")
    logger.info("Year range: %d–%d", year_range.start, year_range.stop - 1)
    logger.info("Vehicles: %d makes, %d models total",
                len(MENA_VEHICLES),
                sum(len(v) for v in MENA_VEHICLES.values()))

    docs: list[Document] = []
    total_requests = 0

    async with httpx.AsyncClient() as client:
        for make, models in MENA_VEHICLES.items():
            for model in models:
                for year in year_range:
                    recalls, complaints = await asyncio.gather(
                        _fetch_recalls(client, make, model, year),
                        _fetch_complaints(client, make, model, year),
                    )
                    total_requests += 2

                    for r in recalls:
                        docs.append(_build_recall_doc(make, model, year, r))

                    if complaints:
                        # Group by component
                        by_comp: dict[str, list[dict[str, Any]]] = {}
                        for c in complaints:
                            comp = c.get("Component", "Unknown")
                            by_comp.setdefault(comp, []).append(c)
                        for comp_complaints in by_comp.values():
                            doc = _build_complaint_doc(make, model, year, comp_complaints)
                            if doc:
                                docs.append(doc)

                    await asyncio.sleep(0.3)

                logger.info(
                    "  %s %s — docs so far: %d (requests: %d)",
                    make, model, len(docs), total_requests
                )

    logger.info("Total documents built: %d", len(docs))

    if dry_run:
        if docs:
            logger.info("[DRY RUN] Sample:\n%s", docs[0].text[:600])
        return

    logger.info("Ingesting %d docs into pojehat_hybrid_v1…", len(docs))
    loop = asyncio.get_running_loop()
    _batch_size = 50
    for i in range(0, len(docs), _batch_size):
        batch = docs[i : i + _batch_size]
        await loop.run_in_executor(None, index_documents, batch)
        logger.info("  Batch %d–%d ingested", i, i + len(batch) - 1)
        await asyncio.sleep(0.5)

    logger.info("✅ NHTSA ingestion complete — %d documents indexed", len(docs))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest NHTSA recall and complaint data into Qdrant"
    )
    parser.add_argument(
        "--years",
        nargs=2,
        type=int,
        default=[2010, 2025],
        metavar=("START", "END"),
        help="Year range to ingest (default: 2010 2025)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch data but do not write to Qdrant",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    yr = range(args.years[0], args.years[1])
    asyncio.run(run_ingestion(year_range=yr, dry_run=args.dry_run))
