"""
Web Ingester Service - Enhanced with rate limiting and retry logic.
"""

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import cast

import httpx
from bs4 import BeautifulSoup
from llama_index.core import Document
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.core.config import settings
from src.domain.pdf_parser import index_documents, ingest_manual

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
HTTP_TIMEOUT = 60.0
DEFAULT_RATE_LIMIT = 1.0  # seconds between requests


class RateLimiter:
    """Simple async rate limiter using semaphore and time-based throttling."""

    def __init__(self, requests_per_second: float = 1.0):
        self.semaphore = asyncio.Semaphore(1)
        self.min_interval = 1.0 / requests_per_second
        self._last_request = 0.0

    async def acquire(self) -> None:
        """Acquire permission to make a request, throttling if needed."""
        async with self.semaphore:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_request = asyncio.get_event_loop().time()


class WebIngester:
    """
    Service to ingest manuals from web URLs.
    Enhanced with rate limiting, retry logic, and connection pooling.
    """

    def __init__(self, requests_per_second: float = 1.0):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self.rate_limiter = RateLimiter(requests_per_second)
        self._session: httpx.AsyncClient | None = None
        self._qdrant_client: AsyncQdrantClient | None = None

    async def _get_qdrant_client(self) -> "AsyncQdrantClient":
        """Get or create Qdrant client."""
        if self._qdrant_client is None:
            from qdrant_client import AsyncQdrantClient

            self._qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
        return self._qdrant_client

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with connection pooling."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                headers=self.headers,
                follow_redirects=True,
                timeout=HTTP_TIMEOUT,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def fetch_manual_links(self, model_url: str) -> list[str]:
        """
        Scrapes a model page for manual attachment links with retries.
        """
        client = await self._get_session()

        for attempt in range(3):
            try:
                await self.rate_limiter.acquire()
                logger.info("Crawling %s (Attempt %d/3)...", model_url, attempt + 1)
                response = await client.get(model_url)

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 7
                    logger.warning("Rate limited. Backing off %ds...", wait_time)
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                links = []

                # The site uses /attachment/ links for manuals
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if "/attachment/" in href or "/manual/" in href:
                        # Resolve relative URLs
                        if not href.startswith("http"):
                            if href.startswith("/"):
                                href = f"https://onlinerepairmanuals.com{href}"
                            else:
                                href = f"{model_url.rstrip('/')}/{href}"
                        links.append(href)

                unique_links = list(set(links))
                logger.info("Found %d manual links.", len(unique_links))
                return unique_links

            except Exception as e:
                if attempt == 2:
                    raise e
                await asyncio.sleep(3)

        return []

    async def extract_pdf_url(self, viewer_url: str) -> str | None:
        """
        Extracts the direct PDF URL from a viewer page.
        Handles Nitro-lazy-loading attributes with retry logic.
        """
        client = await self._get_session()

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_exponential_jitter(initial=1, max=20, jitter=2),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                await self.rate_limiter.acquire()
                try:
                    response = await client.get(viewer_url)
                    if response.status_code != 200:
                        return None

                    soup = BeautifulSoup(response.text, "html.parser")

                    # Try finding iframe with nitro-lazy-src or src
                    iframe = soup.find("iframe", src=re.compile(r"\.pdf")) or soup.find(
                        "iframe", attrs={"nitro-lazy-src": re.compile(r"\.pdf")}
                    )

                    if iframe:
                        pdf_url = iframe.get("nitro-lazy-src") or iframe.get("src")
                        # Clean the URL if it's embedded in viewer.php
                        if "viewer.php?file=" in pdf_url:
                            pdf_url = pdf_url.split("viewer.php?file=")[-1].split("&")[
                                0
                            ]

                        if pdf_url and not pdf_url.startswith("http"):
                            pdf_url = f"https://onlinerepairmanuals.com{pdf_url}"
                        return pdf_url

                    # Check for direct PDF links in meta or script
                    pdf_match = re.search(r'https?://[^\s<>"]+\.pdf', response.text)
                    if pdf_match:
                        return pdf_match.group(0)

                except Exception as e:
                    logger.warning("Error resolving PDF viewer %s: %s", viewer_url, e)

        return None

    async def _download_binary(
        self, pdf_url: str, filename: str | None = None
    ) -> Path:
        """
        Downloads a PDF from a URL to the local upload directory with retry.
        If filename is not provided, it is extracted from the URL.
        """
        if not filename:
            # Extract filename from URL and remove query strings
            filename = pdf_url.split("/")[-1].split("?")[0]
            if not filename:
                # Fallback for root-level URLs
                import hashlib

                filename = f"web_{hashlib.md5(pdf_url.encode()).hexdigest()[:8]}.pdf"

            # Ensure it has a valid extension if we know it's a PDF
            if not any(
                filename.lower().endswith(ext)
                for ext in [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
            ):
                if ".pdf" in pdf_url.lower():
                    filename += ".pdf"

        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        target_path = upload_dir / filename

        client = await self._get_session()

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                await self.rate_limiter.acquire()
                async with client.stream("GET", pdf_url) as response:
                    response.raise_for_status()
                    with open(target_path, "wb") as f:
                        async for chunk in response.aiter_bytes():
                            f.write(chunk)

        return target_path

    async def scrape_with_jina(self, url: str) -> str | None:
        """
        Uses r.jina.ai to convert a URL to clean markdown with retry.
        """
        jina_url = f"https://r.jina.ai/{url}"
        headers = {**self.headers}
        if settings.JINA_API_KEY:
            headers["Authorization"] = f"Bearer {settings.JINA_API_KEY}"

        client = await self._get_session()

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_exponential_jitter(initial=1, max=15, jitter=1),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                try:
                    await self.rate_limiter.acquire()
                    response = await client.get(jina_url, headers=headers)
                    if response.status_code == 200:
                        return response.text
                    logger.warning("Jina error %d for %s", response.status_code, url)
                except Exception as e:
                    logger.warning("Jina fetch failed for %s: %s", url, e)

        return None

    async def scrape_charm_li(
        self, url: str, vehicle_context: str, limit: int = 50
    ) -> int:
        """
        Recursive scraper for charm.li using Jina Reader for markdown conversion.
        Enhanced with better rate limiting.
        """
        logger.info("Jina-Crawl: Recursively scraping charm.li at %s...", url)
        visited = set()
        to_visit: list[str] = [url]
        processed_count: int = 0

        client = await self._get_session()

        while to_visit and processed_count < limit:
            current_url = to_visit.pop(0)
            if current_url in visited:
                continue
            visited.add(current_url)

            try:
                await self.rate_limiter.acquire()
                res = await client.get(current_url)
                if res.status_code != 200:
                    continue

                soup = BeautifulSoup(res.text, "html.parser")

                # Extract sub-links to traverse deeper
                links = soup.find_all("a", href=True)
                sub_links = []
                for a in links:
                    href = a["href"]
                    # Filter to stay within same branch
                    branch_prefix = url.split("charm.li")[-1]
                    if (
                        href.startswith("/")
                        and branch_prefix in f"https://charm.li{href}"
                    ):
                        full_url = f"https://charm.li{href}"
                        if full_url not in visited:
                            sub_links.append(full_url)

                if sub_links:
                    # Depth-First Search feel
                    to_visit = cast(list[str], sub_links) + to_visit

                # Content Extraction using Jina
                # Only process pages that look like terminal content
                if not sub_links or len(soup.find_all("a")) < 15:
                    markdown = await self.scrape_with_jina(current_url)
                    if markdown and len(markdown) > 300:
                        doc = Document(
                            text=markdown,
                            metadata={
                                "source": current_url,
                                "vehicle_context": vehicle_context,
                                "source_type": "jina_scrape",
                            },
                        )
                        await asyncio.get_event_loop().run_in_executor(
                            None, index_documents, [doc]
                        )
                        processed_count += 1
                        if processed_count % 5 == 0:
                            logger.info("Jina ingested %d points...", processed_count)

                # RPM compliance - already handled by rate_limiter
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.warning("Error processing %s: %s", current_url, e)
                continue

        return processed_count

    async def _is_already_ingested(self, url: str) -> bool:
        """
        Checks if the URL has already been ingested into any automotive collection.
        Returns True if a document with metadata source==url exists.
        """

        client = await self._get_qdrant_client()
        # Collections to check (as defined in rag_engine.py)
        collections = ["pojehat_hybrid_v1", "pojehat_obd_ecu_v1"]

        for coll in collections:
            try:
                # Count is more efficient for existence checks
                res = await client.count(
                    collection_name=coll,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="source", match=MatchValue(value=url)
                            )
                        ]
                    ),
                    exact=False,
                )
                if res.count > 0:
                    return True
            except Exception as e:
                # Log error to help debug filter issues
                logger.debug("Qdrant check failed for %coll: %s", coll, e)
                continue
        return False

    async def _process_technical_image_with_vision(
        self, local_path: Path, vehicle_context: str
    ) -> str | None:
        """
        Submits a technical diagram to a Vision model to extract diagnostic text.
        """
        logger.info("Vision-Analysis: Digitizing diagram %s...", local_path.name)

        try:
            with open(local_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")

            payload = {
                "model": settings.VISION_MODEL_NAME,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "You are an automotive electrical engineer. "
                                    f"Extract all technical details from this "
                                    f"{vehicle_context} diagram. "
                                    "Look for connector pinouts, wire colors, "
                                    "fuse IDs, and sensor values. "
                                    "If the image is not a technical diagram, "
                                    "describe it briefly."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error("Vision extraction failed for %s: %s", local_path.name, e)
            return None

    async def _extract_pdf_text_via_ocr(
        self, local_path: Path, vehicle_context: str = "Unknown"
    ) -> str | None:
        """
        Extract text from scanned PDFs using OpenRouter's file-parser plugin
        targeting the Mistral OCR engine.

        Used as a fallback when pymupdf returns zero/garbage text.
        Cost: ~$2.00 per 1k pages. Use judiciously.
        """
        logger.info("OCR-Analysis: Running Mistral OCR on %s...", local_path.name)

        try:
            with open(local_path, "rb") as f:
                base64_file = base64.b64encode(f.read()).decode("utf-8")

            # OpenRouter file-parser plugin payload
            payload = {
                "model": "mistralai/pixtral-large-2411",  # Plugin via model field
                "messages": [{"role": "user", "content": "Extract all text."}],
                "plugins": [
                    {
                        "id": "file-parser",
                        "settings": {
                            "engine": "mistral-ocr",  # High-fidelity automotive OCR
                            "output_format": "markdown",
                        },
                    }
                ],
                "files": [
                    {
                        "content": base64_file,
                        "filename": local_path.name,
                        "mime_type": "application/pdf",
                    }
                ],
            }

            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential_jitter(initial=2, max=10),
                retry=retry_if_exception_type(httpx.HTTPError),
            ):
                with attempt:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            "https://openrouter.ai/api/v1/chat/completions",
                            headers={
                                "Authorization": (
                                    f"Bearer {settings.OPENROUTER_API_KEY}"
                                ),
                                "Content-Type": "application/json",
                            },
                            json=payload,
                        )
                        response.raise_for_status()
                        result = response.json()
                        return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error("Mistral OCR fallback failed for %s: %s", local_path.name, e)
            return None

    async def process_url(self, url: str, vehicle_context: str = "Unknown") -> None:
        """
        High-fidelity ingestion engine for CLI usage.
        Supports direct PDFs, images, Jina-crawls, and viewer fallbacks.
        """
        logger.info("\n%s\n[Pojehat] Processing: %s\n%s", '=' * 60, url, '=' * 60)

        try:
            # Step 0: Deduplication Check (Source Gate)
            if await self._is_already_ingested(url):
                logger.info("URL already exists in knowledge base: %s", url)
                return

            # Case 1: Direct PDF
            if url.lower().endswith(".pdf"):
                filename = url.split("/")[-1]
                local_path = await self._download_binary(url, filename)
                await ingest_manual(str(local_path), vehicle_context=vehicle_context)
                return

            # Case X: Excel / Tabular Data
            if url.lower().endswith((".xlsx", ".xls", ".csv")):
                import pandas as pd

                filename = url.split("/")[-1]
                local_path = await self._download_binary(url, filename)
                logger.info("Parsing Tabular Data: %s", filename)
                try:
                    if filename.endswith(".csv"):
                        df = pd.read_csv(local_path)
                    else:
                        df = pd.read_excel(local_path)

                    markdown_table = df.to_markdown(index=False)
                    from src.domain.pdf_parser import index_documents
                    doc = Document(
                        text=f"TECHNICAL TABLE: {vehicle_context}\n\n{markdown_table}",
                        metadata={
                            "source": url,
                            "vehicle_context": vehicle_context,
                            "source_type": "tabular_data",
                        }
                    )
                    index_documents([doc])
                    logger.info("Ingested spreadsheet: %s", filename)
                except Exception as e:
                    logger.warning("Spreadsheet parsing failed: %s", e)
                return

            # Case Y: Structured JSON (DTCs / Protocols)
            if url.lower().endswith((".json", ".jsonl")):
                filename = url.split("/")[-1]
                local_path = await self._download_binary(url, filename)
                logger.info("Parsing Structured JSON: %s", filename)
                try:
                    with open(local_path) as f:
                        if filename.endswith(".jsonl"):
                            data = [json.loads(line) for line in f]
                        else:
                            data = json.load(f)

                    # Convert to expert-readable MD
                    md_text = f"STRUCTURED TECHNICAL DATA: {vehicle_context}\n"
                    md_text += json.dumps(data, indent=2)

                    doc = Document(
                        text=md_text,
                        metadata={
                            "source": url,
                            "vehicle_context": vehicle_context,
                            "source_type": "structured_json",
                        }
                    )
                    index_documents([doc])
                    logger.info("Ingested JSON data: %s", filename)
                except Exception as e:
                    logger.warning("JSON parsing failed: %s", e)
                return

            # Case 2: Technical Images (Fuses, Pinouts) - UPGRADED WITH VISION
            if any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                from src.domain.pdf_parser import index_documents

                filename = url.split("/")[-1]
                local_path = await self._download_binary(url, filename)
                vision_text = await self._process_technical_image_with_vision(
                    local_path, vehicle_context
                )

                if vision_text:
                    doc = Document(
                        text=vision_text,
                        metadata={
                            "source": url,
                            "vehicle_context": vehicle_context,
                            "source_type": "technical_diagram",
                        },
                    )
                    await asyncio.get_event_loop().run_in_executor(
                        None, index_documents, [doc]
                    )
                    logger.info("Ingested image via Vision: %s", filename)
                else:
                    logger.warning(
                        "Vision extraction failed for %s — skipping.", filename
                    )
                return

            # Case 3: charm.li or similar (HTML Nesting)
            if "charm.li" in url or "workshop-manuals.com" in url:
                count = await self.scrape_charm_li(url, vehicle_context)
                logger.info("Jina-powered crawl ingested %d points.", count)
                return

            # Case 4: Traditional PDF Viewer (manuals.co) or general site
            # Try Jina first for general sites to get clean text
            markdown = await self.scrape_with_jina(url)
            if markdown and len(markdown) > 500:
                from src.domain.pdf_parser import index_documents

                doc = Document(
                    text=markdown,
                    metadata={
                        "source": url,
                        "vehicle_context": vehicle_context,
                        "source_type": "jina_scrape",
                    },
                )
                index_documents([doc])
                logger.info("Ingested %s via Jina Reader.", url)
                return

            # Fallback to manuals.co style redirection
            viewer_links = await self.fetch_manual_links(url)
            pdf_urls = []
            for link in viewer_links[:5]:
                logger.info("Extracting PDF from: %s", link)
                pdf_url = await self.extract_pdf_url(link)
                if pdf_url:
                    pdf_urls.append(pdf_url)
                await asyncio.sleep(2)

            logger.info("Total PDFs to ingest: %d", len(pdf_urls))

            for _i, pdf_url in enumerate(pdf_urls):
                filename = pdf_url.split("/")[-1]
                if not filename.endswith(".pdf"):
                    filename += ".pdf"

                local_path = await self._download_binary(pdf_url, filename)
                result = await ingest_manual(
                    str(local_path), vehicle_context=vehicle_context
                )
                logger.info("Ingested %d pages.", result['pages_processed'])
                await asyncio.sleep(1)

        except Exception as e:
            logger.error("\nWeb ingestion failed: %s", e)
            raise e


web_ingester = WebIngester()
