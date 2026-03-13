"""
Web Ingester Service - Enhanced with rate limiting and retry logic.
"""

import asyncio
import re
from pathlib import Path
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from llama_index.core import Document
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.core.config import settings
from src.domain.pdf_parser import ingest_manual

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

    async def fetch_manual_links(self, model_url: str) -> List[str]:
        """
        Scrapes a model page for manual attachment links with retries.
        """
        client = await self._get_session()

        for attempt in range(3):
            try:
                await self.rate_limiter.acquire()
                print(f"[*] Crawling {model_url} (Attempt {attempt + 1}/3)...")
                response = await client.get(model_url)

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 7
                    print(f"[!] Rate limited. Backing off {wait_time}s...")
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
                print(f"[+] Found {len(unique_links)} manual links.")
                return unique_links

            except Exception as e:
                if attempt == 2:
                    raise e
                await asyncio.sleep(3)

        return []

    async def extract_pdf_url(self, viewer_url: str) -> Optional[str]:
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
                    print(f"[!] Error resolving PDF viewer {viewer_url}: {e}")

        return None

    async def download_pdf(self, pdf_url: str, filename: str) -> Path:
        """
        Downloads a PDF from a URL to the local upload directory with retry.
        """
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

    async def scrape_with_jina(self, url: str) -> Optional[str]:
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
                    print(f"[!] Jina error {response.status_code} for {url}")
                except Exception as e:
                    print(f"[!] Jina fetch failed for {url}: {e}")

        return None

    async def scrape_charm_li(
        self, url: str, vehicle_context: str, limit: int = 50
    ) -> int:
        """
        Recursive scraper for charm.li using Jina Reader for markdown conversion.
        Enhanced with better rate limiting.
        """
        print(f"[*] Jina-Crawl: Recursively scraping charm.li at {url}...")
        visited = set()
        to_visit = [url]
        processed_count = 0
        from src.domain.pdf_parser import index_documents

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
                    to_visit = sub_links + to_visit

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
                        index_documents([doc])
                        processed_count += 1
                        if processed_count % 5 == 0:
                            print(f"[*] Jina ingested {processed_count} points...")

                # RPM compliance - already handled by rate_limiter
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"[!] Error processing {current_url}: {e}")
                continue

        return processed_count

    async def process_url(self, url: str, vehicle_context: str):
        """
        High-fidelity ingestion engine for CLI usage.
        Supports direct PDFs, images, Jina-crawls, and viewer fallbacks.
        """
        print(f"\n{'=' * 60}\n[Pojehat Ingester] Processing: {url}\n{'=' * 60}")

        try:
            # Case 1: Direct PDF
            if url.lower().endswith(".pdf"):
                filename = url.split("/")[-1]
                local_path = await self.download_pdf(url, filename)
                await ingest_manual(str(local_path), vehicle_context=vehicle_context)
                return

            # Case 2: Technical Images (Fuses, Pinouts)
            if any(url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                from src.domain.pdf_parser import index_documents

                filename = url.split("/")[-1]
                local_path = await self.download_pdf(url, filename)
                # For images, we index the metadata and a placeholder
                doc = Document(
                    text=(
                        f"TECHNICAL IMAGE: {vehicle_context} - {filename}\n"
                        f"Source: {url}"
                    ),
                    metadata={
                        "source": url,
                        "vehicle_context": vehicle_context,
                        "local_path": str(local_path),
                        "source_type": "technical_image",
                    },
                )
                index_documents([doc])
                print(f"[SUCCESS] Ingested technical image: {filename}")
                return

            # Case 3: charm.li or similar (HTML Nesting) - Use Jina Recursive Crawl
            if "charm.li" in url or "workshop-manuals.com" in url:
                count = await self.scrape_charm_li(url, vehicle_context)
                print(f"[SUCCESS] Jina-powered crawl ingested {count} points.")
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
                print(f"[SUCCESS] Ingested {url} via Jina Reader.")
                return

            # Fallback to manuals.co style redirection
            viewer_links = await self.fetch_manual_links(url)
            pdf_urls = []
            for link in viewer_links[:5]:
                print(f"[*] Extracting PDF from: {link}")
                pdf_url = await self.extract_pdf_url(link)
                if pdf_url:
                    pdf_urls.append(pdf_url)
                await asyncio.sleep(2)

            print(f"[+] Total PDFs to ingest: {len(pdf_urls)}")

            for i, pdf_url in enumerate(pdf_urls):
                filename = pdf_url.split("/")[-1]
                if not filename.endswith(".pdf"):
                    filename += ".pdf"

                local_path = await self.download_pdf(pdf_url, filename)
                result = await ingest_manual(
                    str(local_path), vehicle_context=vehicle_context
                )
                print(f"[SUCCESS] Ingested {result['pages_processed']} pages.")
                await asyncio.sleep(1)

        except Exception as e:
            print(f"\n[FATAL ERROR] Web ingestion failed: {e}")
            raise e


web_ingester = WebIngester()
