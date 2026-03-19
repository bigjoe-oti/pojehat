# ruff: noqa: E501

"""
Ingestion script for Deep Web academic sources relating to:
- Internal Combustion Engines Modeling and Dynamics
- Automotive Electronic Control Units (ECUs) Architecture
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ACADEMIC_SOURCES = [
    # Engine Dynamics & Modeling
    {
        "url": "https://www.matec-conferences.org/articles/matecconf/pdf/2018/14/matecconf_mms17_02014.pdf",
        "context": "Dynamics of Internal Combustion Engines Made in Downsizing Technology",
    },
    {
        "url": "https://core.ac.uk/download/pdf/132103328.pdf",
        "context": "Enhancing Automotive E/E Architecture with Container-based Electronic Control Units",
    },
    {
        "url": "https://www.phmsociety.org/sites/phmsociety.org/files/phm_submission/2012/phmc_12_056.pdf",
        "context": "Model-based Diagnostics of Automotive Electronic Control Unit (ECU) Ground Faults",
    },
    {
        "url": "https://www.polito.it/sites/default/files/2021-08/ECU%20Testing%20in%20Automotive.pdf",  # Placeholder URL formatting based on Polito's structure
        "context": "ECU Testing and Functional Validation in Automotive Engineering",
    },
]


async def run_academic_ingestion():
    """Execute the Academic Knowledge Expansion Batch."""
    logger.info(
        f"🚀 Launching Academic Ingestion for {len(ACADEMIC_SOURCES)} targets..."
    )

    for item in ACADEMIC_SOURCES:
        url = item["url"]
        context = item["context"]

        logger.info(f"⏳ Academic Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingestion Successful: {context}")
        except Exception as e:
            logger.error(f"❌ Ingestion Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Academic Knowledge Ingestion Complete.")


if __name__ == "__main__":
    asyncio.run(run_academic_ingestion())
