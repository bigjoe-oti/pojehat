"""
Ingest ECU pinout documentation for Egyptian market
priority vehicles. All URLs verified accessible.
Routes to pojehat_hybrid_v1 (default collection).
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

ECU_PINOUT_URLS = [
    {
        "url": (
            "https://ecutools.vn/wp-content/uploads/2024/10/"
            "ECUTools-Vietnam-Pinout-Dimsport-Bench-Mode-"
            "Bosch-ME17.9.21-Husqvarna-KTM.pdf"
        ),
        "context": (
            "Bosch ME17.9.21 ECU Pinout Kia Cerato BD G4FG "
            "TC1724 CAN High Low Power Ground Bench Mode"
        ),
    },
    {
        "url": (
            "https://device.report/m/"
            "fa78788fb3f3eb1d1c16b234fe3ff39b558eeec"
            "444dd5e745193081b26de49db"
        ),
        "context": (
            "Denso Toyota Corolla E210 Hybrid 2ZR-FXE ECU "
            "Wiring Harness Terminal Voltage Sensor Array "
            "Hybrid Control Interface"
        ),
    },
    {
        "url": (
            "https://ecu.design/ecu-pinout/"
            "pinout-hitachi-sh7054-mec37-xxx-nissan/"
        ),
        "context": (
            "Hitachi MEC37 SH7054 ECU Pinout Nissan Sunny B17 "
            "HR15DE 121-Pin Dual Connector Read Write Direct "
            "Connection CAN K-Line"
        ),
    },
    {
        "url": (
            "https://logan-renault.narod.ru/MR388LOGAN1.pdf"
        ),
        "context": (
            "Siemens EMS3132 ECU Pinout Renault Logan K7M "
            "90-Pin Connector TPS Pin 74 75 Injector Pin "
            "89 90 O2 Sensor Fuel Mixture Wiring"
        ),
    },
    {
        "url": (
            "https://ecutools.vn/wp-content/uploads/2024/10/"
            "ECUTools-Vietnam-Pinout-Bosch-ME17.9.11-Hyundai-"
            "Kia.pdf"
        ),
        "context": (
            "Bosch ME17.9.11 ME17.8.8 ECU Pinout Hyundai "
            "Accent G4FC Kia Chery Tiggo E4G15B 94-Pin "
            "Connector K-Line CAN Bootloader"
        ),
    },
    {
        "url": (
            "https://ecu.design/ecu-pinout/"
            "pinout-bosch-me17-9-11-irom-tc1762-egpt-kia-hyundai/"
        ),
        "context": (
            "Bosch ME17.9.11 ECU Pinout Hyundai Accent RB "
            "G4FC Kia Cerato G4FG TC1762 CAN High Low "
            "MAF TPS Injector Pin Assignments"
        ),
    },
    {
        "url": (
            "https://ecu.design/ecu-pinout/"
            "pinout-delphi-mt86-irom-tc1766-kia-hyundai/"
        ),
        "context": (
            "Delphi MT80 MT86 ECU Pinout Peugeot 301 "
            "Citroen C-Elysee EC5 Renault PSA Platform "
            "Connector X1 X2 Dual Plug Signal Ground"
        ),
    },
    {
        "url": (
            "https://ecu.design/ecu-pinout/"
            "pinout-siemens-sid807-xrom-tc1796-psa/"
        ),
        "context": (
            "Siemens SID807 ECU Pinout Peugeot 301 "
            "PSA EC5 1.6L VTi Connector Pin Function "
            "MAP Sensor Knock Sensor O2 VCC Signal"
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

    for item in ECU_PINOUT_URLS:
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
