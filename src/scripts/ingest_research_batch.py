"""
Ingest verified research sources — X431 docs,
wiring references, torque specs, protocol whitepapers.
Routes to pojehat_hybrid_v1 (default collection).
"""
import asyncio
import logging
from src.services.web_ingester import web_ingester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCES = [

    # ── ROUND 1: X431 Documentation ───────────────────────────

    {
        "url": "https://fcc.report/FCC-ID/XUJPADVII/5210037.pdf",
        "context": (
            "Launch X431 PAD VII User Manual Special Functions "
            "Injector Coding EGR Adaptation Gearbox Reset "
            "ABS Bleeding EPB Reset Topology Mapping "
            "Diagnostic Logic Menu Paths"
        ),
    },
    {
        "url": (
            "https://launchtechusa.com/wp-content/uploads/2025/10/"
            "HIGH-RES-Launch_ADAS_1025_v4_FLATTENED-with-spreads.pdf"
        ),
        "context": (
            "Launch X431 ADAS Calibration Guide Static Dynamic "
            "Calibration Front Camera Radar Target Board LAC05-03 "
            "5m 9m Workspace Laser Alignment Procedure"
        ),
    },

    # ── ROUND 2: Wiring — verified non-Scribd sources ─────────

    {
        # Confirmed live — Renault official Dialogys extract
        # Covers K7M engine management, injector pins, TPS pins
        "url": (
            "https://logan-renault.narod.ru/dialogys_pdf/"
            "MR388LOGAN1.pdf"
        ),
        "context": (
            "Renault Logan K7M Siemens EMS3132 ECU Wiring "
            "Engine Management Fuel Injection Ignition "
            "TPS Pin 74 75 Injector Pin 89 90 Cooling "
            "Official Renault Dialogys Service Manual"
        ),
    },

    # ── ROUND 3: Torque and Service Specs ─────────────────────

    {
        "url": "https://www.engine-specs.net/nissan/hr15de.html",
        "context": (
            "Nissan Sunny B17 HR15DE Engine Specifications "
            "Torque Output 134 Nm 4000 RPM Compression Ratio "
            "Valve Clearance Timing Chain Displacement 1498cc"
        ),
    },

    # ── ROUND 4: Protocol Whitepapers ─────────────────────────

    {
        "url": (
            "https://www.dgtech.com/wp-content/uploads/2019/08/"
            "WP1903_UDS_V01.pdf"
        ),
        "context": (
            "UDS Unified Diagnostic Services Whitepaper ISO 14229 "
            "OSI Layer Mapping SID Request Response Frame "
            "Negative Response Code NRC DoCAN DoIP "
            "Security Access Seed Key Programming Session"
        ),
    },
    {
        "url": "https://en.wikipedia.org/wiki/OBD-II_PIDs",
        "context": (
            "SAE J1979 OBD-II PID Reference All Services "
            "PID 0x0C Engine RPM Formula PID 0x0D Speed "
            "PID 0x11 Throttle PID 0x05 Coolant Temp "
            "Hex Scaling Formula Conversion Units"
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
            "AT MA Monitor Mode AT CRA Filter "
            "K-Line ISO Baud Rate OBD Initialization"
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
    before = await client.get_collection("pojehat_hybrid_v1")
    logger.info("hybrid_v1 before: %d points", before.points_count)
    await client.close()

    success, failed, failed_urls = 0, 0, []

    for item in SOURCES:
        logger.info("→ %s", item["context"][:65])
        try:
            await web_ingester.process_url(
                item["url"], item["context"]
            )
            logger.info("  ✓")
            success += 1
        except Exception as e:
            logger.error("  ✗ %s", str(e)[:100])
            failed += 1
            failed_urls.append(item["url"])

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    after = await client.get_collection("pojehat_hybrid_v1")
    logger.info(
        "hybrid_v1 after: %d points (added: %d) | ✓ %d  ✗ %d",
        after.points_count,
        after.points_count - before.points_count,
        success,
        failed,
    )
    if failed_urls:
        for u in failed_urls:
            logger.warning("  FAILED: %s", u)
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
