"""
Bulk Ingester Service - Enhanced with SOTA error handling and retry logic.
"""

import asyncio
import logging
import sys
from typing import Any

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.domain.pdf_parser import ingest_manual
from src.services.web_ingester import WebIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("pojehat.bulk_ingester")

MAX_RETRIES = 5
HTTP_TIMEOUT = 60.0


class BulkIngester:
    """Enhanced bulk ingestion service with retry logic and error handling."""

    def __init__(self):
        self.web_ingester = WebIngester()
        self._session: httpx.AsyncClient | None = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session with connection pooling."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                follow_redirects=True,
                timeout=HTTP_TIMEOUT,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._session

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def scout_fcc_id(self, fcc_id: str) -> None:
        """
        Scrapes fccid.io for internal photos of automotive modules.
        Enhanced with retry logic and better error handling.
        """
        logger.info("[*] Scouring FCC ID: %s for hardware internals...", fcc_id)
        url = f"https://fccid.io/{fcc_id}/internal-photos"

        client = await self._get_session()

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                try:
                    response = await client.get(url)
                    if response.status_code == 404:
                        logger.warning("[!] FCC ID %s not found.", fcc_id)
                        return
                    if response.status_code == 429:
                        wait_time = attempt.retry_state.attempt_number * 10
                        logger.warning(
                            "[!] Rate limited. Backing off %ds...", wait_time
                        )
                        await asyncio.sleep(wait_time)
                        raise httpx.HTTPError("Rate limited")

                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")

                    # Look for direct links to internal photo PDFs
                    links = soup.find_all("a", href=True)
                    target_links = [
                        link_tag["href"]
                        for link_tag in links
                        if "internal" in link_tag["href"].lower()
                        and link_tag["href"].endswith(".pdf")
                    ]

                    if not target_links:
                        logger.warning(
                            "[!] No internal photo PDFs found for %s.", fcc_id
                        )
                        return

                    for link in target_links:
                        absolute_link = (
                            link
                            if link.startswith("http")
                            else f"https://fccid.io{link}"
                        )
                        logger.info("[+] Found Hardware Internal: %s", absolute_link)

                        # Download and ingest with retry
                        try:
                            download_path = await self.web_ingester.download_pdf(
                                absolute_link
                            )
                            if download_path:
                                await ingest_manual(
                                    download_path,
                                    vehicle_context=f"Hardware: {fcc_id}",
                                )
                                logger.info(
                                    "[+] Successfully ingested: %s", absolute_link
                                )
                        except Exception as e:
                            logger.error(
                                "[!] Failed to ingest %s: %s", absolute_link, e
                            )

                except httpx.HTTPStatusError as e:
                    logger.error("[!] HTTP error for %s: %s", fcc_id, e)
                    raise

    async def ingest_targeted_manuals(self, manual_list: list[dict[str, str]]) -> None:
        """
        Ingest a list of manuals with enhanced error handling.

        Args:
            manual_list: list of {"url": str, "context": str}
        """
        results: list[dict[str, Any]] = []

        for item in manual_list:
            url = item.get("url", "")
            context = item.get("context", "Unknown")

            logger.info("[*] Processing Target: %s -> %s", context, url)

            try:
                if url.endswith(".pdf"):
                    # Direct PDF download and ingest
                    d_path = await self._download_with_retry(url)
                    if d_path:
                        await ingest_manual(d_path, vehicle_context=context)
                        results.append({"context": context, "status": "ok"})
                        logger.info("[+] Successfully ingested PDF: %s", context)
                    else:
                        results.append(
                            {
                                "context": context,
                                "status": "failed",
                                "error": "Download failed",
                            }
                        )
                        logger.error("[!] Failed to download: %s", url)

                elif url.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                    # Direct Image download and ingest
                    d_path = await self._download_with_retry(url)
                    if d_path:
                        await ingest_manual(d_path, vehicle_context=context)
                        results.append({"context": context, "status": "ok"})
                        logger.info("[+] Successfully ingested image: %s", context)
                    else:
                        results.append(
                            {
                                "context": context,
                                "status": "failed",
                                "error": "Download failed",
                            }
                        )
                        logger.error("[!] Failed to download image: %s", url)

                else:
                    # Web crawling via WebIngester
                    await self.web_ingester.process_url(url, context)
                    results.append({"context": context, "status": "ok"})
                    logger.info("[+] Successfully crawled: %s", context)

            except Exception as e:
                logger.error("[!] Error ingesting %s: %s", context, str(e))
                results.append(
                    {"context": context, "status": "failed", "error": str(e)}
                )

        # Summary
        ok = sum(1 for r in results if r["status"] == "ok")
        failed = sum(1 for r in results if r["status"] == "failed")
        logger.info("=" * 50)
        logger.info("Bulk Ingestion Summary")
        logger.info("  Succeeded: %d", ok)
        logger.info("  Failed: %d", failed)
        if failed:
            logger.warning("  Failed items:")
            for r in results:
                if r["status"] == "failed":
                    logger.warning(
                        "    - %s: %s", r["context"], r.get("error", "Unknown")
                    )
        logger.info("=" * 50)

    async def _download_with_retry(self, url: str) -> str | None:
        """Download a file with exponential backoff retry."""
        await self._get_session()  # Ensure session is initialized

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            wait=wait_exponential_jitter(initial=1, max=30, jitter=2),
            stop=stop_after_attempt(MAX_RETRIES),
            reraise=True,
        ):
            with attempt:
                try:
                    return await self.web_ingester.download_pdf(url)
                except Exception as e:
                    logger.warning(
                        "[!] Download attempt %d failed for %s: %s",
                        attempt.retry_state.attempt_number,
                        url,
                        e,
                    )
                    raise

        return None

    async def ingest_chipset_datasheets(self, chipsets: list[dict[str, str]]) -> None:
        """
        Ingest chipset datasheets with enhanced error handling.

        Args:
            chipsets: list of {"name": str, "url": str}
        """
        logger.info(
            "[*] Starting chipset datasheet ingestion (%d chips)", len(chipsets)
        )

        results: list[dict[str, Any]] = []

        for chip in chipsets:
            name = chip.get("name", "Unknown")
            url = chip.get("url", "")

            logger.info("[*] Ingesting Chipset Datasheet: %s", name)

            try:
                download_path = await self._download_with_retry(url)
                if download_path:
                    await ingest_manual(
                        download_path, vehicle_context=f"Chipset Datasheet: {name}"
                    )
                    results.append({"name": name, "status": "ok"})
                    logger.info("[+] Successfully ingested chipset: %s", name)
                else:
                    results.append(
                        {"name": name, "status": "failed", "error": "Download failed"}
                    )
                    logger.error("[!] Failed to download chipset: %s", name)
            except Exception as e:
                logger.error("[!] Error ingesting chipset %s: %s", name, str(e))
                results.append({"name": name, "status": "failed", "error": str(e)})

        # Summary
        ok = sum(1 for r in results if r["status"] == "ok")
        failed = sum(1 for r in results if r["status"] == "failed")
        logger.info("Chipset Ingestion: %d ok, %d failed", ok, failed)
