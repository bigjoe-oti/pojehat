import asyncio
import logging
import os

try:
    import transformers.safetensors_conversion
    # FIX: Disable the failing auto-conversion thread that blocks on safetensors PRs
    transformers.safetensors_conversion.auto_conversion = lambda *args, **kwargs: None
except ImportError:
    pass

from src.core.config import settings
from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Phase 3 Targeted Re-ingest Data
PHASE_3_DATA = [
    # BATCH A: DTC Databases
    {
        "url": "https://procarmanuals.com/chery-diagnostic-trouble-codes/",
        "context": "Chery Tiggo DTC Fault Codes Engine Fuel Sensor Injector",
    },
    {
        "url": "https://procarmanuals.com/toyota-diagnostic-trouble-codes-full-list-obd/",
        "context": "Toyota Corolla E210 DTC Fault Codes OBD-II Complete List",
    },
    {
        "url": "https://procarmanuals.com/chevrolet-diagnostic-trouble-codes/",
        "context": "Chevrolet Cruze DTC Fault Codes Engine Transmission",
    },
    # BATCH B: Nissan scanner logic
    {
        "url": "https://nic-tec.com/wp-content/uploads/2019/02/Nissan.pdf",
        "context": "Nissan Sunny B17 Scanner Functions Actuation Tests Data Stream",
    },
    # BATCH C: Chery workshop manual
    {
        "url": "https://cdn-cms.f-static.com/uploads/186686/normal_591193a22097b.pdf",
        "context": "Chery Tiggo Engine Compression Test Electrical Diagnosis Voltage Drop",
    },
    # BATCH D: ECU-specific procedures
    {
        "url": "https://s3cf792cad773e861.jimcontent.com/download/version/1742838309/module/15688750122/name/Toyota%20Engine%20Fault%20Codes%20DTC.pdf",
        "context": "Toyota Corolla E210 Engine Fault Codes DTC P0 P1",
    },
    {
        "url": "https://sc35ef6025435ca24.jimcontent.com/download/version/1677867886/module/9646756682/name/Kia%20OBD_OBD2%20Codes%20%E2%80%93%20Trouble%20Codes.pdf",
        "context": "Kia Cerato BD OBD OBD2 Trouble Codes P0 P1",
    },
    {
        "url": "https://www.dmv.de.gov/VehicleServices/inspections/pdfs/dtc_list.pdf",
        "context": "OBD-II DTC Standard Codes SAE Generic All Systems",
    },
    {
        "url": "https://carmanit.co/wp-content/uploads/2020/12/6.-Signal-Analysis_Oxygen-sensor-MENA.pdf",
        "context": "Oxygen Sensor Signal Analysis Waveforms MENA Egyptian Market",
    },
    {
        "url": "https://carmanit.co/wp-content/uploads/2020/11/2.-Signal-Analysis_Crank-position-sensor-MENA.pdf",
        "context": "Crankshaft Position Sensor Signal Analysis MENA Egyptian Market",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-bosch-me17-9-11-irom-tc1762-egpt-kia-hyundai/",
        "context": "Bosch ME17.9.11 ECU Pinout Kia Hyundai Accent Cerato",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-delphi-mt86-irom-tc1766-kia-hyundai/",
        "context": "Delphi MT86 ECU Pinout Kia Hyundai Renault Logan Peugeot 301",
    },
    {
        "url": "https://ecu.design/ecu-pinout/pinout-siemens-sid807-xrom-tc1796-psa/",
        "context": "Siemens SID807 ECU Pinout Peugeot 301 PSA",
    },
    {
        "url": "https://www.engine-specs.net/nissan/hr15de.html",
        "context": "Nissan Sunny B17 HR15DE Engine Specs Valve Clearance Compression",
    },
    {
        "url": "https://www.csselectronics.com/pages/uds-protocol-tutorial-unified-diagnostic-services",
        "context": "UDS Protocol Unified Diagnostic Services CAN Bus Automotive",
    },
    {
        "url": "https://www.mg.co.uk/sites/default/files/2025-05/MG_ZS_Hybrid_Rescue_Manual.pdf",
        "context": "MG ZS Hybrid SRS Airbag HV High Voltage Safety Disconnect",
    },
    {
        "url": "https://launchtechusa.com/wp-content/uploads/2025/10/X-431-Torque-Link-User-Manual.pdf",
        "context": "Launch X431 Scanner Special Functions Actuation Test Data Stream",
    },
]

async def run_mega_ingest():
    """Run Targeted Re-ingestion for Phase 3."""
    batch = os.getenv("BATCH")
    if batch != "1":
        logger.warning(f"BATCH environment variable is set to {batch}, expected 1. Skipping.")
        return

    # Monkey-patch deduplication to force re-ingestion for Phase 3
    logger.info("🛠️ Monkey-patching web_ingester._is_already_ingested to allow re-ingestion...")
    web_ingester._is_already_ingested = lambda url: asyncio.sleep(0) or False

    # Override target collection for re-ingest
    settings.QDRANT_INGEST_COLLECTION = "pojehat_obd_ecu_v1"
    logger.info(f"Target Collection: {settings.QDRANT_INGEST_COLLECTION}")
    
    logger.info(f"🚀 Starting Targeted Re-Ingestion (Phase 3) for {len(PHASE_3_DATA)} assets...")

    for item in PHASE_3_DATA:
        url = item["url"]
        context = item["context"]
        logger.info(f"⏳ Processing: {context} | URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Success: {context}")
        except Exception as e:
            logger.error(f"❌ Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Targeted Re-Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(run_mega_ingest())
