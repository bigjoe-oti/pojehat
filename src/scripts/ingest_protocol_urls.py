"""
Phase 6: Protocol-Driven URL Ingestion
======================================
Ingests strategic documentation and feature specs from the
'Zero Failure Protocol' to ground the RAG engine.
"""

import asyncio
import logging

from src.services.web_ingester import web_ingester

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

PROTOCOL_TARGETS = [
    {
        "url": "https://carapi.app/docs/",
        "context": "CarAPI V2 Documentation - Vehicle Technical Specs API",
    },
    {
        "url": "https://api.carscan.com/v3.0/tsb?vin=EXAMPLE",
        "context": "CarScan TSB API Structure - Technical Service Bulletins",
    },
    {
        "url": "https://www.carscan.com/technical-service-bulletins/",
        "context": "CarScan TSB Coverage & Features",
    },
    {
        "url": "https://www.motor.com/products/technical-service-bulletins/",
        "context": "Motor.com TSB & Repair Data Features",
    },
    {
        "url": "https://www.infopro-digital-automotive.com/solutions/haynespro/",
        "context": "HaynesPro (WorkshopData) Diagnostic Solutions",
    },
    {
        "url": "https://www.alldata.com/eu/en/repair-europe",
        "context": "ALLDATA Europe - OEM Repair Data & Wiring Diagrams",
    },
    {
        "url": "https://17vin.com/api",
        "context": "17vin.com API Documentation - Asian Market (BYD/Geely/Changan) Decoding",
    },
    {
        "url": "https://www.auto-data.net/en/",
        "context": "Auto-Data.net - Global Vehicle Technical Specifications",
    },
    {
        "url": "https://www.autopoisk.su/api/",
        "context": "Autopoisk.su EPC API - Electronic Parts Catalog Data",
    },
    {
        "url": "https://autoresource.eu/",
        "context": "AutoResource.eu - Parts Catalog & Catalog Integration",
    },
]

async def run_protocol_ingest():
    logger.info("🚀 Launching Protocol-Driven Ingestion (Phase 6)...")
    
    for i, item in enumerate(PROTOCOL_TARGETS):
        url = item["url"]
        ctx = item["context"]
        
        logger.info("⏳ [%d/%d] Ingesting: %s", i + 1, len(PROTOCOL_TARGETS), ctx)
        try:
            # Use Jina-powered scrape for documentation pages
            await web_ingester.process_url(url, vehicle_context=ctx)
            logger.info("✅ Successfully ingested: %s", ctx)
        except Exception as e:
            logger.error("❌ Failed: %s | Error: %s", ctx, e)
            continue
            
    logger.info("🏁 Phase 6 Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(run_protocol_ingest())
