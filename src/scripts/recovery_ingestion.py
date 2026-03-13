import asyncio
from src.services.web_ingester import WebIngester
from src.services.bulk_ingester import BulkIngester

async def recovery():
    wi = WebIngester()
    bi = BulkIngester()
    
    print("\n🆘 Starting Recovery Ingestion Phase...")
    
    # 1. Chipsets (New Mirrors)
    chipsets = [
        {
            "name": "Infineon TriCore SAK-TC1767",
            "url": "https://www.alldatasheet.com/datasheet-pdf/view/215701/INFINEON/SAK-TC1767-256F133HL.html"
        },
        {
            "name": "Renesas SH7058",
            "url": "https://www.alldatasheet.com/datasheet-pdf/view/154467/RENESAS/SH7058.html"
        }
    ]
    
    for chip in chipsets:
        print(f"[*] Recovering Chipset: {chip['name']}...")
        await wi.process_url(chip['url'], f"Chipset Datasheet: {chip['name']}")
    
    # 2. Kia Cerato (Retry with delay)
    print("\n[*] Waiting 10 seconds for rate-limit cooldown (Kia)...")
    await asyncio.sleep(10)
    
    kia_set = [
        {"url": "https://onlinerepairmanuals.com/kia/cerato/", "context": "Kia Cerato (2015-K3)"}
    ]
    await bi.ingest_targeted_manuals(kia_set)
    
    print("\n✅ Recovery ingestion complete.")

if __name__ == "__main__":
    asyncio.run(recovery())
