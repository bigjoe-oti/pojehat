"""
OEM Automotive PDF parser and ingestion module for Pojehat.
Using pymupdf4llm for high-fidelity Markdown extraction.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

import pymupdf4llm
from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

from src.core.config import settings

logger = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _sanitize_text(text: str) -> str:
    """Remove surrogate characters that cannot be encoded in UTF-8."""
    if not isinstance(text, str):
        return text
    return "".join(c for c in text if not (0xD800 <= ord(c) <= 0xDFFF))


def _derive_domain_tag(vehicle_context: str) -> str:
    """
    Derive a broad domain tag from vehicle_context for payload filtering.
    Used post-ingestion to route gap-aware retrieval queries. (B3)
    """
    from src.core.config import EGYPTIAN_MARKET_VEHICLES  # avoid circular import

    vc_lower = vehicle_context.lower()
    if any(
        k in vc_lower
        for k in ["transmission", "cvt", "gearbox", "jatco", "a6mf", "a6lf"]
    ):
        return "transmission"
    if any(
        k in vc_lower
        for k in ["hv", "ev", "electric", "hybrid", "battery", "zsev", "zs ev"]
    ):
        return "hv_ev"
    if any(k in vc_lower for k in ["srs", "airbag", "air bag", "restraint"]):
        return "srs"
    if any(
        k in vc_lower
        for k in ["can", "uds", "doip", "lin", "protocol", "iso 14229"]
    ):
        return "protocol"
    if any(
        k in vc_lower
        for k in [
            "pinout", "ecu pinout", "connector",
            "me17", "mt80", "mt86", "sid807",
        ]
    ):
        return "ecu_pinout"
    if any(k in vc_lower for k in ["dtc", "fault code", "trouble code", "obd"]):
        return "dtc_database"
    if any(
        k in vc_lower
        for k in ["sensor", "waveform", "maf", "oxygen", "crank", "cam"]
    ):
        return "sensor_specs"
    if any(k in vc_lower for k in ["wiring", "electrical", "circuit", "schematic"]):
        return "wiring"
    for vehicle in EGYPTIAN_MARKET_VEHICLES:
        if vehicle.lower().split()[0] in vc_lower:
            return "oem_manual"
    return "general"


# ── Validation guard ──────────────────────────────────────────────────────────

_VAGUE_CONTEXTS: frozenset[str] = frozenset(
    {"unknown", "general", "", "none", "n/a"}
)


# ── Ingestion Logic ───────────────────────────────────────────────────────────


async def ingest_manual(
    file_path: str, vehicle_context: str = "Unknown"
) -> dict[str, str | int]:
    """
    Parse an automotive PDF using pymupdf4llm for high-fidelity extraction
    and push structured chunks to Qdrant. Includes OCR fallback.
    """
    # REC-2: Warn on vague vehicle_context — domain_tag will default to 'general'
    if vehicle_context.strip().lower() in _VAGUE_CONTEXTS:
        logger.warning(
            "ingest_manual called with vague vehicle_context=%r — "
            "domain_tag will default to 'general'. "
            "Provide specific context for gap-aware retrieval filtering.",
            vehicle_context,
        )

    doc_path = Path(file_path)
    if not doc_path.exists():
        return {"status": "error", "message": f"File not found: {file_path}"}

    loop = asyncio.get_event_loop()

    # 1. High-fidelity Markdown extraction via pymupdf4llm (Run in executor)
    try:
        md_text = await loop.run_in_executor(
            None, lambda: pymupdf4llm.to_markdown(str(doc_path))
        )
        md_text = _sanitize_text(md_text)
    except Exception as e:
        return {"status": "error", "message": f"Extraction failed: {str(e)}"}

    # FIX 9D: OCR Fallback for scanned/poorly parsed PDFs
    if len(md_text.strip()) < 200:
        from src.services.web_ingester import web_ingester
        ocr_text = await web_ingester._extract_pdf_text_via_ocr(
            doc_path, vehicle_context
        )
        if ocr_text:
            md_text = ocr_text

    # 2. Create LlamaIndex Document
    stable_key = f"{doc_path.name}"
    doc_id = hashlib.sha256(stable_key.encode()).hexdigest()

    metadata = {
        "file_name": doc_path.name,
        "vehicle_context": vehicle_context[:80],
        "source_type": "pdf_manual",
        "domain_tag": _derive_domain_tag(vehicle_context),  # B3
    }

    document = Document(
        text=md_text,
        metadata=metadata,
        doc_id=doc_id,
        excluded_embed_metadata_keys=["file_name"],
        excluded_llm_metadata_keys=["file_name"],
    )

    # 3. Indexing (Run in executor to prevent blocking)
    await loop.run_in_executor(None, index_documents, [document])

    return {
        "status": "success",
        "file": doc_path.name,
        "collection": settings.QDRANT_INGEST_COLLECTION,
    }


def _get_vector_store_and_index() -> tuple[OpenAIEmbedding, StorageContext]:
    """Return embed model + Qdrant storage context for the configured collection."""
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = settings.QDRANT_INGEST_COLLECTION

    collections = client.get_collections()
    if not any(c.name == collection_name for c in collections.collections):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # text-embedding-3-small native size
                distance=models.Distance.COSINE
            ),
        )

    # B2: Index payload fields for gap-aware retrieval filtering
    collection_info = client.get_collection(collection_name)
    existing_indexes = []
    if collection_info.payload_schema:
        # qdrant_client < 1.7.0 returns dict, 1.7.0+ returns PayloadSchema
        if isinstance(collection_info.payload_schema, dict):
            existing_indexes = list(collection_info.payload_schema.keys())
        else:
            # Handle object-based schema if present
            existing_indexes = list(getattr(collection_info.payload_schema, "schema", {}).keys())

    for field_name in [
        "source",
        "vehicle_context",
        "file_name",
        "domain_tag",    # broad domain (transmission, hv, protocol, etc.)
        "source_type",   # already set in metadata — now indexed for filtering
    ]:
        if field_name not in existing_indexes:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                logger.debug(f"Index for {field_name} already exists or failed: {e}")

    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        enable_hybrid=False, # Stabilize: Disable sparse embeddings causing HF/Transformers errors
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return embed_model, storage_context


def index_documents(documents: list[Document]) -> None:
    """Index documents with optimized chunking."""
    if not documents:
        return
    embed_model, storage_context = _get_vector_store_and_index()
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
        transformations=[SentenceSplitter(chunk_size=1024, chunk_overlap=128)],
    )
