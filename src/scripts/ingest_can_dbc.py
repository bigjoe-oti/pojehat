"""
Ingest CAN DBC signal database files.
Routes to pojehat_obd_ecu_v1 via env override.
Using corrected URLs for commaai/opendbc master branch.
"""
import asyncio
import logging
import os
import sys

# Ensure the project root is in sys.path
sys.path.append(os.getcwd())

# Override collection BEFORE importing src
os.environ["QDRANT_INGEST_COLLECTION"] = "pojehat_obd_ecu_v1"

from src.services.web_ingester import web_ingester  # noqa: E402
from src.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DBC_URLS = [
    {
        "url": (
            "https://raw.githubusercontent.com/commaai/"
            "opendbc/master/opendbc/dbc/hyundai_kia_generic.dbc"
        ),
        "context": (
            "Hyundai Kia Generic CAN DBC Signal Database "
            "Powertrain Body Chassis Messages Engine_Data "
            "Wheel_Speeds_11 Steering_Buttons_Data "
            "Egyptian Market Diagnostic Reference"
        ),
    },
    {
        "url": (
            "https://raw.githubusercontent.com/commaai/"
            "opendbc/master/opendbc/dbc/generator/toyota/"
            "toyota_nodsu_pt.dbc"
        ),
        "context": (
            "Toyota Corolla E210 Hybrid Powertrain CAN DBC "
            "Signal Matrix GAS_COMMAND STEERING_CONTROL "
            "ACC_CONTROL Pitch Yaw Roll Motor_Torque "
            "HV_Battery_Level Scaling Factor Offset"
        ),
    },
    {
        "url": (
            "https://raw.githubusercontent.com/commaai/"
            "opendbc/master/opendbc/dbc/toyota_tss2_adas.dbc"
        ),
        "context": (
            "Toyota TSS2 ADAS CAN DBC Signal Matrix "
            "Lane Keep Assist Forward Collision Warning "
            "Radar Data Camera Data 0x12F 0x226 Message IDs "
            "Corolla Hybrid E210 Egyptian Market"
        ),
    },
]


async def main() -> None:
    from qdrant_client import AsyncQdrantClient

    # Confirm override worked
    assert settings.QDRANT_INGEST_COLLECTION == "pojehat_obd_ecu_v1", \
        "Collection override failed"

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        before = await client.get_collection("pojehat_obd_ecu_v1")
        logger.info(
            "obd_ecu_v1 before: %d points",
            before.points_count
        )
    finally:
        await client.close()

    success, failed = 0, 0

    for item in DBC_URLS:
        logger.info("→ Processing DBC: %s...", item["context"][:65])
        try:
            # We use process_url which handles deduplication and high-quality indexing
            await web_ingester.process_url(
                item["url"], item["context"]
            )
            logger.info("  ✓ SUCCESS")
            success += 1
        except Exception as e:
            logger.error("  ✗ FAILED: %s", str(e)[:100])
            failed += 1

    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )
    try:
        after = await client.get_collection("pojehat_obd_ecu_v1")
        logger.info(
            "obd_ecu_v1 after: %d points (added: %d) "
            "| ✓ %d  ✗ %d",
            after.points_count,
            after.points_count - before.points_count,
            success, failed,
        )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
