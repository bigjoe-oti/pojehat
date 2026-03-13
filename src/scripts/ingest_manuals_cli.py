import argparse
import asyncio
import sys

from src.services.web_ingester import WebIngester
from src.services.bulk_ingester import BulkIngester


async def main():
    parser = argparse.ArgumentParser(description="Pojehat SOTA Web Ingestion CLI")
    parser.add_argument(
        "--url", type=str, help="URL of the manual or model page"
    )
    parser.add_argument(
        "--context", 
        type=str, 
        default="Unknown Vehicle", 
        help="Vehicle context (e.g. 'Hyundai Accent 2011')"
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Limit number of manuals to process"
    )
    parser.add_argument(
        "--bulk", 
        action="store_true", 
        help="Ingest predefined bulk technical set (Nissan, Chevy, Chery, Kia)"
    )
    parser.add_argument(
        "--fccid", 
        type=str, 
        help="Deep-dive hardware research for a specific FCC ID (e.g. KR5TC1)"
    )
    
    args = parser.parse_args()

    print("\n🚀 Initializing Pojehat Ingestion Pipeline...")
    
    bi = BulkIngester()

    if args.bulk:
        print("🚙 Starting Bulk Technical Ingestion (Tier-3 Mode)...")
        technical_set = [
            {
                "url": "https://onlinerepairmanuals.com/nissan/sentra/",
                "context": "Nissan Sentra (B17/B18)",
            },
            {
                "url": "https://onlinerepairmanuals.com/nissan/qashqai/",
                "context": "Nissan Qashqai (J11/J12)",
            },
            {
                "url": "https://onlinerepairmanuals.com/chevrolet/cruze/",
                "context": "Chevrolet Cruze (2014-2026)",
            },
            {
                "url": "https://onlinerepairmanuals.com/kia/cerato/",
                "context": "Kia Cerato (2015-K3)",
            },
            # Chipsets
            {
                "url": (
                    "https://www.infineon.com/dgdl/Infineon-TC1767-DS-v01_01-en.pdf"
                    "?fileId=db3a304323c21c7d0123cb1d318e472d"
                ),
                "context": "Chipset: Infineon TriCore SAK-TC1767",
            },
            {
                "url": (
                    "https://www.alldatasheet.com/datasheet-pdf/view/154467/RENESAS/"
                    "SH7058.html"
                ),
                "context": "Chipset: Renesas SH7058",
            },
        ]
        await bi.ingest_targeted_manuals(technical_set)
        print("\n✅ Bulk ingestion completed.")
    
    elif args.fccid:
        print(f"🔍 Starting Hardware Deep-Dive for FCC ID: {args.fccid}...")
        await bi.scout_fcc_id(args.fccid)
        print("\n✅ Hardware research completed.")

    elif args.url:
        print(f"📍 Target: {args.url}")
        print(f"🚙 Context: {args.context}")
        ingester = WebIngester()
        try:
            await ingester.process_url(args.url, args.context)
            print("\n✅ Ingestion pipeline completed successfully.")
        except Exception as e:
            print(f"\n❌ Ingestion pipeline failed: {e}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    asyncio.run(main())
