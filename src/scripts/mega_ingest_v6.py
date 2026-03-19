# ruff: noqa: E501

"""
Mega-Ingestion V6: Automotive Intelligence Expansion.
Targeting high-fidelity Haynes manuals, vision-processed wiring diagrams,
structured code databases, and localized Egyptian market data.
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEGA_DATA_V6 = [
    # --- PDFs & Technical Manuals ---
    {
        "url": "http://www.sd5.nl/zelf/haynes/Ford--Haynes--Ford_Focus_Diesel_2005_to_2009.pdf",
        "context": "Ford Focus Diesel (2005-2009) Haynes Manual / Torque Specs",
    },
    {
        "url": "https://www.landrover.com/Images/Defender-200Tdi-200MY-TechSpec_tcm29-115167.pdf",
        "context": "Land Rover Defender 200Tdi Technical Specifications",
    },
    {
        "url": "https://www.nissan-techinfo.com/refgh0v/om/FR/2023-Nissan-Versa-Sedan-FR.pdf",
        "context": "Nissan Versa Sedan (2023) OEM Manual / B17 Equivalent",
    },
    {
        "url": "https://www.motor.com/products-services/data-products/technical-service-bulletins/",
        "context": "MOTOR Technical Service Bulletins (TSB) Portal",
    },
    {
        "url": "https://www.hyundai.com/content/dam/hyundai/ww/en/images/owners/technology/wiring/hyundai-electrical-wiring-diagrams-elantra-2021.pdf",
        "context": "Hyundai Elantra (2021) OEM Wiring Diagrams",
    },

    # --- JSON & Structured Data ---
    {
        "url": "https://flespi.com/protocols/spireon?sort=parameter_name",
        "context": "Flespi Spireon Protocol / CAN DTC Schema",
    },
    {
        "url": "https://www.opendiag.com/en/download/free-dtc-database",
        "context": "OpenDiag Structured DTC Database",
    },
    {
        "url": "https://github.com/OpenJAL/JAL-Files/blob/master/automotive/obd_codes.json",
        "context": "GitHub OpenJAL OBD Codes Database",
    },

    # --- PNG, Images & Diagrams (Vision-Enhanced) ---
    {
        "url": "https://imgbin.com/png/zJjCXCas/hino-dutro-m02csf-car-drawing-png",
        "context": "Hino Dutro Engine Wiring Routing / Position of Parts",
    },
    {
        "url": "https://vsepredohraniteli.ru/toyota/corolla-12g.html",
        "context": "Toyota Corolla E210 Fuse & Relay Schematics",
    },
    {
        "url": "https://www.chery.ru/owners/support/warranty/garantiinye-pravila-modeli-chery-tiggo-7l-c-18-04-2025/",
        "context": "Chery Tiggo 7 Technical Components & Warranty Data",
    },
    {
        "url": "https://www.renault.com.co/vehiculos/logan/especificaciones.html",
        "context": "Renault Logan Technical Specs (Torque/Injection)",
    },
    {
        "url": "https://www.bitauto.com/wiki/100124027012/",
        "context": "Peugeot 301 E-Manual / Circuit Atlas",
    },

    # --- HTML & Localized Egyptian Data ---
    {
        "url": "https://www.hatla2ee.com/",
        "context": "Hatla2ee: Egyptian Car Market / Regional Trims",
    },
    {
        "url": "https://www.nissan-egypt.com/cars/sunny.html",
        "context": "Nissan Sunny (B17) Egyptian Factory Specifications",
    },
    {
        "url": "https://www.mg-motor.eg/models/mg-zs/",
        "context": "MG ZS Egyptian Market Technical Data",
    },
    {
        "url": "https://www.peugeot.com.eg/showroom/301-sedan.html",
        "context": "Peugeot 301 Egyptian Factory Features/Specs",
    },
    {
        "url": "https://www.renault.com.eg/vehicles/logan.html",
        "context": "Renault Logan Egyptian Factory Technical Data",
    },

    # --- XLSX & Tabular Data ---
    {
        "url": "https://www.onlinedown.net/soft/10014042.htm",
        "context": "Automobile Maintenance Item Detail Table (XLSX)",
    },
    {
        "url": "https://www.aa1car.com/library/torque_specs_chart.xls",
        "context": "Engine/Chassis Torque Specifications Chart (Excel)",
    },
    {
        "url": "https://www.autodata.com/products/technical-data",
        "context": "Autodata Technical Data Portal",
    },
]


async def run_mega_ingest_v6():
    """Execute the Advanced Automotive Ingestion (V6)."""
    logger.info(
        f"🚀 Launching Mega-Ingestion (V6): Advanced Intelligence Expansion for {len(MEGA_DATA_V6)} targets..."
    )

    for i, item in enumerate(MEGA_DATA_V6):
        url = item["url"]
        context = item["context"]

        logger.info(f"⏳ [{i+1}/{len(MEGA_DATA_V6)}] Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingested: {context}")
        except Exception as e:
            logger.error(f"❌ Failed: {context} | Error: {str(e)}")
            continue

    logger.info("🏁 Mega-Ingestion V6 Complete.")


if __name__ == "__main__":
    asyncio.run(run_mega_ingest_v6())
