"""
Ingestion script for hardcoded public diagnostic codes into pojehat_hybrid_v1.

Uses deterministic SHA-256 doc_id per diagnostic code so re-running this
script upserts existing points rather than creating duplicates.
"""

import hashlib
import logging
import sys

from llama_index.core import Document, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.core.config import settings

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Publicly available raw texts for CVT & Lamp codes
PUBLIC_SOURCES = {
    "P0868": (
        "Transmission Fluid Pressure Low. Causes: Low CVT fluid, "
        "Failing CVT fluid pump, Internal CVT pressure leak."
    ),
    "P0776": (
        "Pressure Control Solenoid B Performance. Causes: Dirty CVT fluid, "
        "Solenoid failure, Valve body binding."
    ),
    "P17F0": (
        "CVT Judder (Inspection Return). Causes: Steel belt scoring, "
        "pulley wear. Requires CVT replacement."
    ),
    "P17F1": (
        "CVT Judder (Inspection). Causes: Minor belt slip. "
        "May require valve body replacement or reprogramming."
    ),
    "B2580": (
        "Headlamp Control Module Malfunction. "
        "Causes: Corroded ALCM connector, failed matrix LED driver."
    ),
    "B2581": (
        "Right Low Beam Circuit Open. "
        "Causes: Blown bulb, severed wiring, blown fuse."
    ),
    "U0164": (
        "Lost Communication With HVAC Control Module. "
        "Causes: CAN bus fault, bad ground to HVAC unit."
    ),
    "P2765": (
        "Input/Turbine Speed Sensor B Circuit. "
        "Causes: Defective speed sensor, damaged wiring harness."
    ),
    "P0746": (
        "Pressure Control Solenoid A Performance. "
        "Causes: CVT valve body failure, severe fluid contamination."
    ),
    "B0028": (
        "Right Side Airbag Deployment Control. "
        "Causes: Impact sensor short to ground, clockspring failure."
    ),
    # Egyptian Market Top-Sellers
    "P17F1_JATCO": (
        "[Nissan Sunny/Sentra Jatco CVT7] CVT Judder (Inspection). "
        "Symptoms: Severe jerking on acceleration. "
        "Causes: Damaged pushbelt or scored pulley. "
        "Fix: Valve body replacement or full transmission swap."
    ),
    "P088200": (
        "[Chery Tiggo 7 Pro CVT25] TCU System Undervoltage. "
        "Symptoms: Gearbox malfunction error on dash, limp mode. "
        "Causes: Failing alternator, bad ground at TCM, software glitch."
    ),
    "P0700_MG": (
        "[MG ZS 7DCT] Transmission Control System Malfunction. "
        "Symptoms: Vehicle remains stationary despite gear selection. "
        "Causes: Guide cable failure inside DCT, clutch overheating."
    ),
    "P0218_CHERY": (
        "[Chery Tiggo 5X/7] Transmission Over Temperature Condition. "
        "Symptoms: Slipping, stiffness, dashboard warning. "
        "Causes: Degraded CVT18/CVT25 fluid, heavy urban stop-and-go stress."
    ),
    "TRQ_CONV_K120": (
        "[Toyota Corolla E210 K120 CVT] Torque Converter Failure. "
        "Symptoms: RPM fluctuation, delayed engagement at 20k miles. "
        "Causes: Sealed unit fluid degradation, premature mechanical failure."
    ),
}


def get_index() -> VectorStoreIndex:
    """Initialise the vector index for the pojehat_hybrid_v1 collection."""
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = "pojehat_hybrid_v1"

    try:
        client.get_collection(collection_name)
    except Exception:
        logger.info("Collection %s not found. Creating.", collection_name)
        client.create_collection(
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
        client=client,
        enable_hybrid=True,
    )
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )


def main() -> None:
    """Ingest all public diagnostic codes with idempotent upsert."""
    try:
        index = get_index()
        logger.info("Initializing Public Diagnostics ingestion...")

        documents: list[Document] = []
        for code, desc in PUBLIC_SOURCES.items():
            content = f"Diagnostic Trouble Code: {code}\nDescription: {desc}"
            # Deterministic doc_id — upserts on re-run, never duplicates
            doc_id = hashlib.sha256(f"pubdiag|{code}".encode()).hexdigest()
            doc = Document(
                text=content,
                metadata={
                    "source": "public_diagnostic_database",
                    "category": "hybrid_drivetrain_and_electrical",
                    "code": code,
                },
                doc_id=doc_id,
            )
            documents.append(doc)

        logger.info("Upserting %d diagnostic documents into Qdrant...", len(documents))

        # refresh_ref_docs upserts by doc_id — idempotent, zero duplicates
        index.refresh_ref_docs(documents)

        logger.info("Public Diagnostic Ingestion Complete.")

    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
