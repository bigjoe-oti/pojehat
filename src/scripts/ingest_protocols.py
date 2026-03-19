"""
Ingest standardized automotive diagnostic protocol
references. SAE J1979, ISO 14229 UDS, ELM327 AT
commands, and ISO 15765-2 ISO-TP transport layer.
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

PROTOCOL_URLS = [
    {
        "url": "https://en.wikipedia.org/wiki/OBD-II_PIDs",
        "context": (
            "SAE J1979 OBD-II PID Reference Service 01 02 "
            "03 04 09 All Standard PIDs 0x00 to 0xFF "
            "Hex Formula Scaling Units Engine RPM Speed "
            "MAF Coolant O2 Fuel Trim"
        ),
    },
    {
        "url": (
            "https://www.csselectronics.com/pages/"
            "uds-protocol-tutorial-unified-diagnostic-services"
        ),
        "context": (
            "ISO 14229 UDS Protocol Client Server Architecture "
            "Service 0x10 Session 0x11 Reset 0x19 DTC "
            "0x22 Read Data 0x27 Security Access 0x2E "
            "Write 0x31 Routine Control Seed Key"
        ),
    },
    {
        "url": (
            "https://cdn.sparkfun.com/assets/4/e/5/0/2/"
            "ELM327_AT_Commands.pdf"
        ),
        "context": (
            "ELM327 AT Commands v2.2 Serial CAN Bridge "
            "AT Z Reset AT SP Protocol AT SH Header "
            "AT CRA Filter AT MA Monitor AT IB ISO Baud "
            "OBD-II Initialization Sequence"
        ),
    },
    {
        "url": (
            "https://canlogger.csselectronics.com/tools-docs/"
            "decoders_mf4/transportprotocol/isotp.html"
        ),
        "context": (
            "ISO 15765-2 ISO-TP Transport Protocol Single "
            "Frame First Frame Flow Control Consecutive "
            "Frame Multi-Frame CAN 8-Byte Payload "
            "Fragmentation Reassembly Block Size STmin"
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

    for item in PROTOCOL_URLS:
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
