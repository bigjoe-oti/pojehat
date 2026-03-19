"""
Ingest Launch X431 and OBDonUDS documentation.
Covers 31+ special functions, ADAS calibration,
and UDS implementation in diagnostic tools.
"""
import asyncio
import logging
import sys
import os

# Ensure the project root is in sys.path
sys.path.append(os.getcwd())

from src.services.web_ingester import web_ingester

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

X431_URLS = [
    {
        "url": (
            "https://launcheurope.de/launcheurope/wp-content/"
            "uploads/2020/10/"
            "X-431-EURO-PRO-5-User-Manual-EN.pdf"
        ),
        "context": (
            "Launch X431 Pro5 EuroPro5 User Manual Special "
            "Functions Injector Coding EPB Reset Throttle "
            "Adaptation SAS Calibration TPMS Relearn "
            "Gearbox Learning VCI Pairing"
        ),
    },
    {
        "url": (
            "https://www.launchtech.co.uk/resources/files/"
            "2022-launchuk-web-catalogue-not4print.pdf"
        ),
        "context": (
            "Launch X431 PAD VII Pro5 Special Functions "
            "31 Maintenance Functions Menu Paths DoIP "
            "CAN FD Online Programming ECU Coding "
            "Egyptian Market Diagnostic Tool"
        ),
    },
    {
        "url": (
            "https://launchtechusa.com/wp-content/uploads/"
            "2025/10/"
            "HIGH-RES-Launch_ADAS_1025_v4_FLATTENED-"
            "with-spreads.pdf"
        ),
        "context": (
            "Launch X431 ADAS Calibration Guide Static "
            "Dynamic Calibration Front Camera Radar "
            "Target Board LAC05-03 5m 9m Workspace "
            "Laser Alignment Procedure"
        ),
    },
    {
        "url": (
            "https://etools.org/wp-content/uploads/2024/09/"
            "OBDonUDS.pdf"
        ),
        "context": (
            "OBDonUDS UDS Implementation Guide 3-Byte DTC "
            "Structure Freeze Frame First Occurrence Latest "
            "Occurrence ISO 14229 Diagnostic Tool Protocol"
        ),
    },
]


async def main() -> None:
    from qdrant_client import AsyncQdrantClient
    from src.core.config import settings

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        before = await client.get_collection("pojehat_hybrid_v1")
        logger.info(
            "hybrid_v1 before: %d points", before.points_count
        )
    finally:
        await client.close()

    success, failed, failed_urls = 0, 0, []

    for item in X431_URLS:
        logger.info("→ Processing: %s...", item["context"][:65])
        try:
            await web_ingester.process_url(
                item["url"], item["context"]
            )
            logger.info("  ✓ SUCCESS")
            success += 1
        except Exception as e:
            logger.error("  ✗ FAILED: %s", str(e)[:100])
            failed += 1
            failed_urls.append(item["url"])

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        after = await client.get_collection("pojehat_hybrid_v1")
        logger.info(
            "hybrid_v1 after: %d points (added: %d) "
            "| ✓ %d  ✗ %d",
            after.points_count,
            after.points_count - before.points_count,
            success, failed,
        )
        if failed_urls:
            for u in failed_urls:
                logger.warning("  FAILED URL: %s", u)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
