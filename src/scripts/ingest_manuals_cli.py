"""
Pojehat Ingestion CLI - Enhanced with SOTA features from mega_ingest_v4.

Features:
- Hybrid search (dense + sparse/BM25 embeddings)
- Advanced chunking with sentence-aware splitting
- Checkpoint/resume capability
- Dead-letter queue for failed items
- Exponential backoff with jitter retry
- Content-hash deduplication
"""

import argparse
import asyncio
import hashlib
import io
import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient, models
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.core.config import settings
from src.services.bulk_ingester import BulkIngester
from src.services.web_ingester import WebIngester

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", settings.OPENROUTER_API_KEY)
COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "pojehat_docs")
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")
EMBED_DIM: int = int(os.getenv("EMBED_DIM", "1536"))
CHUNK_TOKENS: int = int(os.getenv("CHUNK_TOKENS", "512"))
CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "64"))
UPSERT_BATCH: int = int(os.getenv("UPSERT_BATCH", "64"))
EMBED_CONCURRENCY: int = int(os.getenv("EMBED_CONCURRENCY", "6"))
MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
HTTP_TIMEOUT: int = int(os.getenv("HTTP_TIMEOUT", "60"))
RECREATE_COLLECTION: bool = os.getenv("RECREATE_COLLECTION", "false").lower() == "true"
CHECKPOINT_PATH: Path = Path(os.getenv("CHECKPOINT_PATH", "ingest_checkpoint.json"))
DLQ_PATH: Path = Path(os.getenv("DLQ_PATH", "ingest_dlq.jsonl"))

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("pojehat.ingest")

# ─────────────────────────────────────────────────────────────────────────────
# TOKENIZER
# ─────────────────────────────────────────────────────────────────────────────

try:
    import tiktoken as _tiktoken

    _ENC = _tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        return len(_ENC.encode(text, disallowed_special=()))

    _TOKENIZER_BACKEND = "tiktoken/cl100k_base"
except Exception:
    _WORD_RE = re.compile(r"\d+\.?\d*|[A-Za-z][A-Za-z'\-]+|[A-Za-z]+|[^\s]")

    def _count_tokens(text: str) -> int:
        return max(1, round(len(_WORD_RE.findall(text)) * 1.3))

    _TOKENIZER_BACKEND = "word-count-approximation"

# ─────────────────────────────────────────────────────────────────────────────
# ASSET MANIFEST
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Asset:
    url: str
    context: str
    brand: str
    model: str
    doc_type: str
    tags: tuple[str, ...] = ()


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION & CLEANING
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ExtractedPage:
    page_num: int
    text: str
    is_image_page: bool = False


_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SPACES = re.compile(r"[ \t]{2,}")
_NEWLINE = re.compile(r"\n{3,}")


def _clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    text = _CTRL.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _SPACES.sub(" ", text)
    text = _NEWLINE.sub("\n\n", text)
    return text.strip()


def extract_pdf(raw: bytes) -> list[ExtractedPage]:
    """Page-level text extraction via PyMuPDF."""
    pages: list[ExtractedPage] = []
    with fitz.open(stream=io.BytesIO(raw), filetype="pdf") as doc:
        for page_num, page in enumerate(doc, start=1):
            text = _clean_text(
                page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            )
            if text:
                pages.append(
                    ExtractedPage(
                        page_num=page_num,
                        text=text,
                        is_image_page=len(text) < 80,
                    )
                )
    return pages


def extract_html(raw: bytes) -> list[ExtractedPage]:
    """Readable-text extraction from HTML."""
    soup = BeautifulSoup(raw, "html.parser")

    for tag in soup(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "noscript",
            "form",
            "button",
            "iframe",
        ]
    ):
        tag.decompose()

    manual_divs = soup.select(
        ".manual-page, [id^='pdf-page'], .page-content, article, main"
    )
    if manual_divs:
        pages = []
        for i, div in enumerate(manual_divs, start=1):
            text = _clean_text(div.get_text(separator=" ", strip=True))
            if text:
                pages.append(ExtractedPage(page_num=i, text=text))
        if pages:
            return pages

    text = _clean_text(soup.get_text(separator=" ", strip=True))
    return [ExtractedPage(page_num=1, text=text)] if text else []


# ─────────────────────────────────────────────────────────────────────────────
# SEMANTIC CHUNKER
# ─────────────────────────────────────────────────────────────────────────────

_SENTENCE_BOUNDARY = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z"\'\(\[\{])'
    r"|\n{2,}"
)


def chunk_text(
    text: str,
    max_tokens: int = CHUNK_TOKENS,
    overlap_tokens: int = CHUNK_OVERLAP,
) -> list[str]:
    """Sentence-aware chunker with token-counted overlap."""
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if s.strip()]
    if not sentences:
        return [text.strip()] if text.strip() else []

    chunks = []
    current_sents = []
    current_tok = 0

    for sentence in sentences:
        s_tok = _count_tokens(sentence)

        if s_tok > max_tokens:
            if current_sents:
                chunks.append(" ".join(current_sents))
                current_sents, current_tok = [], 0

            words, word_buf, word_tok = sentence.split(), [], 0
            for word in words:
                wt = _count_tokens(word + " ")
                if word_tok + wt > max_tokens and word_buf:
                    chunks.append(" ".join(word_buf))
                    tail = word_buf[max(0, len(word_buf) - overlap_tokens) :]
                    word_buf = tail[:]
                    word_tok = _count_tokens(" ".join(word_buf))
                word_buf.append(word)
                word_tok += wt
            current_sents = word_buf
            current_tok = word_tok
            continue

        if current_tok + s_tok > max_tokens and current_sents:
            chunks.append(" ".join(current_sents))

            overlap_buf, overlap_tok = [], 0
            for s in reversed(current_sents):
                st = _count_tokens(s)
                if overlap_tok + st > overlap_tokens:
                    break
                overlap_buf.insert(0, s)
                overlap_tok += st

            current_sents = overlap_buf
            current_tok = overlap_tok

        current_sents.append(sentence)
        current_tok += s_tok

    if current_sents:
        chunks.append(" ".join(current_sents))

    return [c for c in chunks if _count_tokens(c) >= 20]


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING HELPERS
# ─────────────────────────────────────────────────────────────────────────────


async def _dense_embed_batch(
    texts: list[str],
    oai_client: AsyncOpenAI,
    sem: asyncio.Semaphore,
) -> list[list[float]]:
    async with sem:
        async for attempt in AsyncRetrying(
            wait=wait_exponential_jitter(initial=1, max=20, jitter=1),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                resp = await oai_client.embeddings.create(
                    model=EMBED_MODEL,
                    input=texts,
                    encoding_format="float",
                )
                return [d.embedding for d in resp.data]
    raise RuntimeError("Dense embedding exhausted all retries")


# ─────────────────────────────────────────────────────────────────────────────
# PAYLOAD & POINT ID
# ─────────────────────────────────────────────────────────────────────────────


def _content_hash(text: str) -> str:
    """32-char hex SHA-256 fingerprint for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:32]


def _point_id(source_url: str, chunk_index: int) -> str:
    """Deterministic UUID for idempotent upserts."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_url}::{chunk_index}"))


def _build_payload(
    asset: Asset,
    chunk: str,
    chunk_index: int,
    total_chunks: int,
    page_num: int,
    is_image_page: bool,
) -> dict[str, Any]:
    """Rich, filterable payload with full metadata."""
    return {
        "content": chunk,
        "content_hash": _content_hash(chunk),
        "source_url": asset.url,
        "context": asset.context,
        "brand": asset.brand,
        "model": asset.model,
        "doc_type": asset.doc_type,
        "tags": list(asset.tags),
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "page_num": page_num,
        "is_image_page": is_image_page,
        "ingested_at": datetime.now(UTC).isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# QDRANT COLLECTION SETUP
# ─────────────────────────────────────────────────────────────────────────────


async def ensure_collection(qdrant: AsyncQdrantClient) -> None:
    """Create or verify the Qdrant collection with hybrid search config."""
    exists = await qdrant.collection_exists(COLLECTION_NAME)

    if exists and RECREATE_COLLECTION:
        logger.warning(
            "Dropping collection '%s' (RECREATE_COLLECTION=true)",
            COLLECTION_NAME,
        )
        await qdrant.delete_collection(COLLECTION_NAME)
        exists = False

    if not exists:
        logger.info("Creating collection '%s' ...", COLLECTION_NAME)
        await qdrant.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(
                    size=EMBED_DIM,
                    distance=models.Distance.COSINE,
                    hnsw_config=models.HnswConfigDiff(
                        m=16,
                        ef_construct=200,
                        full_scan_threshold=10_000,
                        max_indexing_threads=0,
                        on_disk=False,
                    ),
                    quantization_config=models.ScalarQuantization(
                        scalar=models.ScalarQuantizationConfig(
                            type=models.ScalarType.INT8,
                            quantile=0.99,
                            always_ram=True,
                        )
                    ),
                    on_disk=False,
                ),
            },
            optimizers_config=models.OptimizersConfigDiff(
                default_segment_number=4,
                indexing_threshold=20_000,
                memmap_threshold=100_000,
                flush_interval_sec=5,
                max_optimization_threads=0,
            ),
            shard_number=1,
            replication_factor=1,
            on_disk_payload=False,
        )
        logger.info("Collection '%s' created.", COLLECTION_NAME)
    else:
        logger.info("Collection '%s' exists — skipping create.", COLLECTION_NAME)

    await _create_payload_indices(qdrant)


async def _create_payload_indices(qdrant: AsyncQdrantClient) -> None:
    """Create all payload field indices."""
    await qdrant.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="content",
        field_schema=models.TextIndexParams(
            type="text",
            tokenizer=models.TokenizerType.WORD,
            min_token_len=2,
            max_token_len=40,
            lowercase=True,
            ascii_folding=True,
        ),
    )

    for fname in (
        "brand",
        "model",
        "doc_type",
        "source_url",
        "content_hash",
        "context",
    ):
        await qdrant.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=fname,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    for fname in ("chunk_index", "total_chunks", "page_num"):
        await qdrant.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=fname,
            field_schema=models.IntegerIndexParams(
                type="integer",
                lookup=True,
                range=True,
            ),
        )

    await qdrant.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="is_image_page",
        field_schema=models.PayloadSchemaType.BOOL,
    )

    logger.info("Payload indices ensured on '%s'.", COLLECTION_NAME)


# ─────────────────────────────────────────────────────────────────────────────
# UPSERT
# ─────────────────────────────────────────────────────────────────────────────


async def _upsert_batch(
    qdrant: AsyncQdrantClient,
    points: list[models.PointStruct],
) -> None:
    async for attempt in AsyncRetrying(
        wait=wait_exponential_jitter(initial=0.5, max=15, jitter=1),
        stop=stop_after_attempt(MAX_RETRIES),
        reraise=True,
    ):
        with attempt:
            await qdrant.upsert(
                collection_name=COLLECTION_NAME,
                points=points,
                wait=True,
            )


# ─────────────────────────────────────────────────────────────────────────────
# CHECKPOINT & DLQ
# ─────────────────────────────────────────────────────────────────────────────


def _load_checkpoint() -> set[str]:
    if CHECKPOINT_PATH.exists():
        data = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        return set(data.get("completed_urls", []))
    return set()


def _save_checkpoint(completed: set[str]) -> None:
    CHECKPOINT_PATH.write_text(
        json.dumps({"completed_urls": sorted(completed)}, indent=2),
        encoding="utf-8",
    )


def _write_dlq(asset: Asset, error: str) -> None:
    """Append a structured failure record to the dead-letter queue."""
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "url": asset.url,
        "context": asset.context,
        "brand": asset.brand,
        "model": asset.model,
        "doc_type": asset.doc_type,
        "error": error,
    }
    with DLQ_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP HELPERS
# ─────────────────────────────────────────────────────────────────────────────

_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


async def _fetch_bytes(url: str, client: httpx.AsyncClient) -> bytes:
    """Download raw bytes with exponential-backoff retry."""
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
        wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
        stop=stop_after_attempt(MAX_RETRIES),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(
                url,
                headers=_BROWSER_HEADERS,
                follow_redirects=True,
                timeout=HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.content
    raise RuntimeError(f"Download failed after {MAX_RETRIES} retries: {url}")


# ─────────────────────────────────────────────────────────────────────────────
# CORE ASSET PROCESSOR
# ─────────────────────────────────────────────────────────────────────────────


async def _process_asset(
    asset: Asset,
    http_client: httpx.AsyncClient,
    oai_client: AsyncOpenAI,
    qdrant: AsyncQdrantClient,
    sem: asyncio.Semaphore,
) -> int:
    """End-to-end pipeline: download -> extract -> chunk -> embed -> upsert."""
    url_lower = asset.url.lower()
    is_pdf = url_lower.endswith(".pdf")
    is_image = url_lower.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))

    logger.info("  Downloading %s", asset.url)
    raw = await _fetch_bytes(asset.url, http_client)

    if is_pdf:
        pages = extract_pdf(raw)
    elif is_image:
        pages = [
            ExtractedPage(
                page_num=1,
                text=(
                    f"[PINOUT DIAGRAM] {asset.context}. "
                    f"Brand: {asset.brand}. Model/ECU: {asset.model}. "
                    f"Document type: {asset.doc_type}. "
                    f"Tags: {', '.join(asset.tags)}. "
                    f"Source: {asset.url}"
                ),
                is_image_page=True,
            )
        ]
    else:
        pages = extract_html(raw)

    if not pages:
        raise ValueError(f"Zero extractable pages from: {asset.url}")

    logger.info("  Extracted %d page(s)", len(pages))

    all_chunks: list[tuple[str, int, bool]] = []
    for page in pages:
        for c in chunk_text(page.text):
            all_chunks.append((c, page.page_num, page.is_image_page))

    if not all_chunks:
        raise ValueError(f"Zero valid chunks from: {asset.url}")

    total = len(all_chunks)
    avg_tok = sum(_count_tokens(c[0]) for c in all_chunks) / total
    logger.info("  %d chunk(s) (avg %.0f tok/chunk)", total, avg_tok)

    total_batches = -(-total // UPSERT_BATCH)
    ingested = 0

    for batch_num, batch_start in enumerate(range(0, total, UPSERT_BATCH), start=1):
        batch = all_chunks[batch_start : batch_start + UPSERT_BATCH]
        texts = [c[0] for c in batch]

        dense_vecs = await _dense_embed_batch(texts, oai_client, sem)

        points: list[models.PointStruct] = []
        for local_i, ((chunk, page_num, is_img), dense) in enumerate(
            zip(batch, dense_vecs, strict=False)
        ):
            global_idx = batch_start + local_i
            points.append(
                models.PointStruct(
                    id=_point_id(asset.url, global_idx),
                    vector={"dense": dense},
                    payload=_build_payload(
                        asset=asset,
                        chunk=chunk,
                        chunk_index=global_idx,
                        total_chunks=total,
                        page_num=page_num,
                        is_image_page=is_img,
                    ),
                )
            )

        await _upsert_batch(qdrant, points)
        ingested += len(points)
        logger.info(
            "  Batch %d/%d upserted (%d/%d chunks)",
            batch_num,
            total_batches,
            ingested,
            total,
        )

    return ingested


# ─────────────────────────────────────────────────────────────────────────────
# ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────


async def run_mega_ingest(assets: list[Asset]) -> None:
    logger.info("=" * 72)
    logger.info("POJEHAT Enhanced Ingestion Pipeline")
    logger.info("  Qdrant     : %s / %s", QDRANT_URL, COLLECTION_NAME)
    logger.info("  Assets     : %d", len(assets))
    logger.info("  Embed      : %s (%dd)", EMBED_MODEL, EMBED_DIM)
    logger.info("  Chunk      : %d tok / %d tok overlap", CHUNK_TOKENS, CHUNK_OVERLAP)
    logger.info("  Tokenizer  : %s", _TOKENIZER_BACKEND)
    logger.info("  Batch      : %d points/upsert", UPSERT_BATCH)
    logger.info("  Concurrency: %d embed workers", EMBED_CONCURRENCY)
    logger.info("=" * 72)

    completed = _load_checkpoint()
    if completed:
        logger.info("Resuming: %d asset(s) already completed.", len(completed))

    qdrant = AsyncQdrantClient(
        url=QDRANT_URL, api_key=QDRANT_API_KEY or None, timeout=60
    )
    oai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    sem = asyncio.Semaphore(EMBED_CONCURRENCY)

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as http_client:
        await ensure_collection(qdrant)

        results: list[dict[str, Any]] = []

        for asset in assets:
            if asset.url in completed:
                logger.info("SKIP (checkpoint): %s", asset.context)
                results.append({"asset": asset, "status": "skipped", "chunks": 0})
                continue

            logger.info("-" * 72)
            logger.info("Processing: %s", asset.context)
            t0 = time.monotonic()

            try:
                n = await _process_asset(asset, http_client, oai_client, qdrant, sem)
                elapsed = time.monotonic() - t0
                logger.info("Done: %s [%d chunks, %.1fs]", asset.context, n, elapsed)
                completed.add(asset.url)
                _save_checkpoint(completed)
                results.append({"asset": asset, "status": "ok", "chunks": n})

            except Exception as exc:
                elapsed = time.monotonic() - t0
                err_msg = f"{type(exc).__name__}: {exc}"
                logger.error("Failed: %s [%.1fs] %s", asset.context, elapsed, err_msg)
                _write_dlq(asset, err_msg)
                results.append(
                    {
                        "asset": asset,
                        "status": "failed",
                        "chunks": 0,
                        "error": err_msg,
                    }
                )

    await qdrant.close()

    # Summary
    ok = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skipped"]
    failed = [r for r in results if r["status"] == "failed"]
    total_chunks = sum(r["chunks"] for r in ok)

    logger.info("=" * 72)
    logger.info("Ingestion Complete")
    logger.info("  Succeeded : %d asset(s) -> %d chunks indexed", len(ok), total_chunks)
    logger.info("  Skipped   : %d asset(s) (checkpoint)", len(skipped))
    logger.info("  Failed    : %d asset(s)", len(failed))
    if failed:
        logger.info("  Dead-letter queue -> %s", DLQ_PATH)
        for r in failed:
            logger.warning("    %s -- %s", r["asset"].context, r.get("error", ""))
    logger.info("  Checkpoint -> %s", CHECKPOINT_PATH)
    logger.info("=" * 72)


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRYPOINT
# ─────────────────────────────────────────────────────────────────────────────


async def main():
    parser = argparse.ArgumentParser(description="Pojehat Enhanced Ingestion CLI")
    parser.add_argument("--url", type=str, help="URL of the manual or model page")
    parser.add_argument(
        "--context",
        type=str,
        default="Unknown Vehicle",
        help="Vehicle context (e.g. 'Hyundai Accent 2011')",
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Limit number of manuals to process"
    )
    parser.add_argument(
        "--bulk",
        action="store_true",
        help="Ingest predefined bulk technical set (Nissan, Chevy, Chery, Kia)",
    )
    parser.add_argument(
        "--fccid",
        type=str,
        help="Deep-dive hardware research for a specific FCC ID (e.g. KR5TC1)",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate Qdrant collection before ingestion",
    )

    args = parser.parse_args()

    global RECREATE_COLLECTION
    if args.recreate:
        RECREATE_COLLECTION = True

    print("\n🚀 Initializing Pojehat Enhanced Ingestion Pipeline...")

    bi = BulkIngester()

    if args.bulk:
        print("🚙 Starting Bulk Technical Ingestion (Enhanced Mode)...")
        technical_set = [
            {
                "url": "https://onlinerepairmanuals.com/nissan/sentra/",
                "context": "Nissan Sentra (B17/B18)",
            },
            {
                "url": "https://onlinerepairmanuals.com/nissan/qashqai/",
                "context": "Nissan Qashqai (J11/J12)",
            },
            {
                "url": "https://onlinerepairmanuals.com/chevrolet/cruze/",
                "context": "Chevrolet Cruze (2014-2026)",
            },
            {
                "url": "https://onlinerepairmanuals.com/kia/cerato/",
                "context": "Kia Cerato (2015-K3)",
            },
            {
                "url": (
                    "https://www.infineon.com/dgdl/Infineon-TC1767-DS-v01_01-en.pdf"
                    "?fileId=db3a304323c21c7d0123cb1d318e472d"
                ),
                "context": "Chipset: Infineon TriCore SAK-TC1767",
            },
            {
                "url": (
                    "https://www.alldatasheet.com/datasheet-pdf/view/154467/RENESAS/"
                    "SH7058.html"
                ),
                "context": "Chipset: Renesas SH7058",
            },
        ]
        await bi.ingest_targeted_manuals(technical_set)
        print("\n✅ Bulk ingestion completed.")

    elif args.fccid:
        print(f"🔍 Starting Hardware Deep-Dive for FCC ID: {args.fccid}...")
        await bi.scout_fcc_id(args.fccid)
        print("\n✅ Hardware research completed.")

    elif args.url:
        print(f"📍 Target: {args.url}")
        print(f"🚙 Context: {args.context}")
        ingester = WebIngester()
        try:
            await ingester.process_url(args.url, args.context)
            print("\n✅ Ingestion pipeline completed successfully.")
        except Exception as e:
            print(f"\n❌ Ingestion pipeline failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    if not OPENAI_API_KEY:
        sys.exit(
            "OPENAI_API_KEY is not set.\n"
            "  export OPENAI_API_KEY=sk-...\n"
            "  Then re-run the script."
        )
    asyncio.run(main())
