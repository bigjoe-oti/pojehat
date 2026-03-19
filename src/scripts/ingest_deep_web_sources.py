# ruff: noqa: E501

"""
Ingestion script for Deep Web sources relating to:
- Engine Cooling and Thermal Management
- Automotive Electronics Reliability
- ECU Hardware Design & Functional Safety
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEEP_WEB_SOURCES = [
    # Engine Cooling & Thermal Management
    {
        "url": "https://www.sae.org/publications/technical-papers/content/2002-01-0713/",
        "context": "SAE 2002-01-0713: Coolant Flow Control Strategies for Automotive Thermal Management Systems",
    },
    {
        "url": "https://www.sae.org/publications/technical-papers/content/2011-24-0067/",
        "context": "SAE 2011-24-0067: Heat Transfers in an Engine's Cooling System",
    },
    {
        "url": "https://www.diva-portal.org/smash/get/diva2:1154569/FULLTEXT01.pdf",  # Valid public thesis on cooling
        "context": "Automotive Engine Cooling System Optimization",
    },
    # Automotive Electronics Reliability
    {
        "url": "https://www.nhtsa.gov/sites/nhtsa.gov/files/documents/812436_reliability-electronic-control-sys.pdf",
        "context": "NHTSA: Reliability of Automotive Electronic Control Systems",
    },
    {
        "url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.500-333.pdf",  # Proxy for reliability
        "context": "NIST/NHTSA Automotive Hardware Reliability Standards",
    },
    # ECU Hardware Design & Functional Safety
    {
        "url": "https://www.nxp.com/docs/en/application-note/AN13229.pdf",
        "context": "NXP AN13229: Hardware Design Guidelines for S32G2 Vehicle Network Processors",
    },
    {
        "url": "https://www.nxp.com/docs/en/application-note/AN12882.pdf",
        "context": "NXP AN12882: Hardware Design Guidelines for S32K3xx Microcontrollers",
    },
    {
        "url": "https://www.infineon.com/dgdl/Infineon-AURIX_TC3xx_Hardware_Design_Guidelines-ApplicationNotes-v01_03-EN.pdf?fileId=5546d4626cb27db2016cebf451451e60",
        "context": "Infineon AURIX TC3xx Hardware Design Guidelines (ECU Microcontrollers)",
    },
    {
        "url": "https://www.st.com/resource/en/application_note/an5269-hardware-design-guidelines-for-spc58-2b-line-microcontrollers-stmicroelectronics.pdf",
        "context": "STMicroelectronics SPC58 Hardware Design Guidelines for Automotive",
    },
]


async def run_deep_web_ingestion():
    """Execute the Deep Web Knowledge Expansion Batch."""
    logger.info(
        f"🚀 Launching Deep Web Ingestion for {len(DEEP_WEB_SOURCES)} targets..."
    )

    for item in DEEP_WEB_SOURCES:
        url = item["url"]
        context = item["context"]

        logger.info(f"⏳ Deep Web Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            # We use the existing web_ingester which hits Jina Reader under the hood
            # and automatically routes to the oem_manuals_v2 (or pojehat_docs) Qdrant collection
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingestion Successful: {context}")
        except Exception as e:
            logger.error(f"❌ Ingestion Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Deep Web Knowledge Ingestion Complete.")


if __name__ == "__main__":
    asyncio.run(run_deep_web_ingestion())
