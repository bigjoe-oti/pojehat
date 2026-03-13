"""
Mega-Ingestion Orchestration Script for Pojehat (V3 - Ingestion Stabilized).
Processes 14 brands using high-reliability mirrors and direct storage links.
Bypasses 403 bot blocks by targeting direct PDF storage where possible.
"""

import asyncio
import logging
from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEGA_DATA = [
    # 1. Hyundai - Direct Storage Discovery
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5525112.pdf",
        "context": "Hyundai Elantra (MD/AD) Manual"
    },
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5525113.pdf",
        "context": "Hyundai Accent (RB) Manual"
    },
    {
        "url": (
            "https://vignette.wikia.nocookie.net/external-ecu-pinouts/"
            "images/6/6a/Hyundai_ME17.9.11.png"
        ),
        "context": "Hyundai Bosch ME17.9.11 Pinout"
    },

    # 2. Nissan - Direct Storage Discovery
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5530025.pdf",
        "context": "Nissan Sunny (N17) Manual"
    },
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5529944.pdf",
        "context": "Nissan Sentra (B17) Manual"
    },

    # 3. Chevrolet
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5524887.pdf",
        "context": "Chevrolet Cruze Manual"
    },
    {
        "url": "https://www.manualslib.com/manual/1474136/Chevrolet-Cruze.html?page=1530",
        "context": "Chevrolet Cruze ACDelco E39 Pinout"
    },

    # 4. Kia
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5529665.pdf",
        "context": "Kia Cerato Manual"
    },
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5529712.pdf",
        "context": "Kia Sportage Manual"
    },

    # 5. Mitsubishi
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5530441.pdf",
        "context": "Mitsubishi Lancer EX Manual"
    },

    # 6. Renault
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5530889.pdf",
        "context": "Renault Logan Manual"
    },

    # 7. Chery
    {
        "url": "https://www.manualslib.com/manual/1004111/Chery-Tiggo.html",
        "context": "Chery Tiggo Manual"
    },

    # 8. VAG Group
    {
        "url": "https://onlinerepairmanuals.com/wp-content/uploads/2025/04/5531442.pdf",
        "context": "Skoda Octavia A7 Manual"
    },

    # 9. MG
    {
        "url": "https://www.manualslib.com/manual/2967657/Mg-Mg5.html",
        "context": "MG 5 Manual"
    }
]

async def run_mega_ingest():
    """Run the batch ingestion for multiple technical assets."""
    logger.info(f"🚀 Starting Mega-Ingestion (V3) for {len(MEGA_DATA)} assets...")
    
    for item in MEGA_DATA:
        url = item["url"]
        context = item["context"]
        logger.info(f"⏳ Processing: {context} | URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Success: {context}")
        except Exception as e:
            logger.error(f"❌ Failed: {context} | Error: {str(e)}")
            continue
            
    logger.info("🏁 Mega-Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(run_mega_ingest())
