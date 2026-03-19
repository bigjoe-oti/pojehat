# ruff: noqa: E501

"""
Ingestion script for accessible PDF sources relating to:
- Systems Design of Electronic Control Units
- Automotive Mechanical and Electrical Architecture integration
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACCESSIBLE_SOURCES = [
    {
        # A public technical document on internal combustion heat transfers often mirrored openly
        "url": "https://www.energy.gov/sites/prod/files/2014/03/f13/deer11_woschni.pdf",
        "context": "Heat Transfer in Internal Combustion Engines (Woschni)",
    },
    {
        # Detailed vehicle dynamics and safety ECU implementations
        "url": "https://www.nhtsa.gov/sites/nhtsa.gov/files/documents/812436_reliability-electronic-control-sys.pdf",
        "context": "Reliability of Automotive Electronic Control Systems (NHTSA)",
    },
    {
        # General electric/electronic architecture in modern vehicles
        "url": "https://www.can-cia.org/fileadmin/resources/documents/proceedings/2008_caspar.pdf",
        "context": "Automotive Electric/Electronic Architecture (CAN-CiA)",
    },
    {
        # Detailed ECU design paradigms
        "url": "https://www.st.com/resource/en/application_note/cd00178345-automotive-microcontrollers-for-engine-management-stmicroelectronics.pdf",  # Trying a different ST struct
        "context": "Automotive Microcontrollers for Engine Management (ST)",
    },
]


async def run_accessible_ingestion():
    """Execute the Open Knowledge Expansion Batch."""
    logger.info(
        f"🚀 Launching Accessible Ingestion for {len(ACCESSIBLE_SOURCES)} targets..."
    )

    for item in ACCESSIBLE_SOURCES:
        url = item["url"]
        context = item["context"]

        logger.info(f"⏳ Accessible Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingestion Successful: {context}")
        except Exception as e:
            logger.error(f"❌ Ingestion Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Open Knowledge Ingestion Complete.")


if __name__ == "__main__":
    asyncio.run(run_accessible_ingestion())
