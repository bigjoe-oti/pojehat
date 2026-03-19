"""
Bulk ingestion script for Egyptian automotive targets.
Extracts actual PDF/image URLs from Google search links and ingests them.
"""

import asyncio
import re

from src.services.bulk_ingester import BulkIngester


def extract_actual_url(google_url: str) -> str:
    """
    Extract actual PDF/image URL from Google search URL.
    Example: https://www.google.com/search?q=https://carmanualshub.com/...pdf
    -> https://carmanualshub.com/...pdf
    """
    # Simple extraction - look for http(s) after q=
    match = re.search(r"q=(https?://[^&]+)", google_url)
    if match:
        return match.group(1)
    # If no match, return original (might already be direct URL)
    return google_url


# Egyptian automotive targets grouped by brand
EGYPTIAN_TARGETS = [
    # NISSAN - N17 Sunny (Egypt's #1 car)
    {
        "url": "https://owners.nissanusa.com/content/techpub/ManualsAndGuides/VersaSedan/2018/2018-VersaSedan-owner-manual.pdf",
        "context": "Nissan Sunny N17 (Versa Sedan) 2018 Owner's Manual",
        "brand": "Nissan",
        "model": "Sunny N17",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://www-asia.nissan-cdn.net/content/dam/Nissan/ph/brochures/Owners/N17%20OM20E00N17G0.pdf",
        "context": "Nissan Sunny N17 Service & Training Manual",
        "brand": "Nissan",
        "model": "Sunny N17",
        "doc_type": "service_manual",
    },
    # {
    #     "url": "https://fusesdiagram.com/wp-content/uploads/2017/01/EN-NissanSunny-N17-block-kapot.jpg",
    #     "context": "Nissan Sunny N17 Fuse Box Diagram",
    #     "brand": "Nissan",
    #     "model": "Sunny N17",
    #     "doc_type": "fuse_diagram",
    # },
    # HYUNDAI - Verna (Accent)
    {
        "url": "https://www.hyundai.com/content/dam/hyundai/in/en/data/connect-to-service/owners-manual/2025/vernamar2023-present.pdf",
        "context": "Hyundai Verna (Accent) 2023-Present Owner's Manual",
        "brand": "Hyundai",
        "model": "Verna",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://www.hyundai.com/content/dam/hyundai/in/en/data/connect-to-service/owners-manual/elantra.pdf",
        "context": "Hyundai General Service Reference (Elantra Commonality)",
        "brand": "Hyundai",
        "model": "General",
        "doc_type": "service_manual",
    },
    # TOYOTA - Corolla
    {
        "url": "http://toyota.aitnet.org/Toyota/Corolla/Corolla_E11_Haynes_Workshop_Manual.pdf",
        "context": "Toyota Corolla Haynes Workshop Manual (Common EWD)",
        "brand": "Toyota",
        "model": "Corolla",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.toyota.com/owners/resources/warranty-owners-manuals.corolla.2015.pdf",
        "context": "Toyota Corolla 2015 Service & Repair Manual",
        "brand": "Toyota",
        "model": "Corolla 2015",
        "doc_type": "service_manual",
    },
    # CHERY - Tiggo 7 / 8 / 4 Pro
    {
        "url": "https://d1urf3gtyt803p.cloudfront.net/public/owner-manual/Tiggo7+Pro.pdf",
        "context": "Chery Tiggo 7 Pro Owner's Manual",
        "brand": "Chery",
        "model": "Tiggo 7 Pro",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://d1urf3gtyt803p.cloudfront.net/public/owner-manual/Tiggo4+Pro.pdf",
        "context": "Chery Tiggo 4 Pro Owner's Manual",
        "brand": "Chery",
        "model": "Tiggo 4 Pro",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://chery.co.za/wp-content/uploads/2022/02/Tiggo-8-Pro-Brochure-2.pdf",
        "context": "Chery Tiggo 8 Pro Technical Brochure & Specifications",
        "brand": "Chery",
        "model": "Tiggo 8 Pro",
        "doc_type": "technical_doc",
    },
    # MG - 5 / ZS
    {
        "url": "https://www.mg.co.uk/sites/default/files/2024-11/MG-ZS-Petrol-Hybrid-Owner-Manual.pdf",
        "context": "MG ZS Petrol/Hybrid Owner's Manual",
        "brand": "MG",
        "model": "ZS",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://mgmotors.dk/wp-content/uploads/2021/04/MG-ZS-EV-Owner-Manual_full.pdf",
        "context": "MG ZS EV Owner's Manual",
        "brand": "MG",
        "model": "ZS EV",
        "doc_type": "owner_manual",
    },
    # RENAULT - Logan
    {
        "url": "https://cyber.cse.iitk.ac.in/PAGE$/96FD698/41FD678265/manual__renault_logan__2007.pdf",
        "context": "Renault Logan 2007 Owner's Manual",
        "brand": "Renault",
        "model": "Logan",
        "doc_type": "owner_manual",
    },
    {
        "url": "https://www.press.renault.co.uk/assets/documents/original/13931-FactsFigures2018.pdf",
        "context": "Renault Technical Facts & Figures 2018",
        "brand": "Renault",
        "model": "General",
        "doc_type": "technical_doc",
    },
    # FIAT - Tipo
    {
        "url": "http://download.fiatforum.bg/Books/Tipo_Tempra/Manual.pdf",
        "context": "Fiat Tipo Service & Repair Manual",
        "brand": "Fiat",
        "model": "Tipo",
        "doc_type": "service_manual",
    },
    {
        "url": "https://finecars.am/brochure/43ee78643f5c4fab6094a2e6d70fc948.pdf",
        "context": "Fiat Tipo Owner's Handbook",
        "brand": "Fiat",
        "model": "Tipo",
        "doc_type": "owner_manual",
    },
    # ECU HARDWARE SPECIFICS
    {
        "url": "https://ecu-connections.com/wp-content/uploads/2022/bosch-me17-pinout.pdf",
        "context": "Bosch ME17 ECU Pinout",
        "brand": "Bosch",
        "model": "ME17",
        "doc_type": "ecu_pinout",
    },
    {
        "url": "https://vignette.wikia.nocookie.net/external-ecu-pinouts/images/6/6a/Hyundai_ME17.9.11.png",
        "context": "Hyundai ME17.9.11 ECU Pinout",
        "brand": "Hyundai",
        "model": "ME17.9.11",
        "doc_type": "ecu_pinout",
    },
]


async def main():
    """Ingest all Egyptian automotive targets."""
    print("🚗 Starting Egyptian Automotive Targets Ingestion")
    print(f"📊 Total targets: {len(EGYPTIAN_TARGETS)}")

    # Extract actual URLs from Google search links
    targets = []
    for target in EGYPTIAN_TARGETS:
        actual_url = extract_actual_url(target["url"])
        targets.append(
            {
                "url": actual_url,
                "context": target["context"],
            }
        )
        print(f"  • {target['brand']} {target['model']}: {actual_url[:80]}...")

    # Initialize bulk ingester
    ingester = BulkIngester()

    try:
        # Ingest all targets
        await ingester.ingest_targeted_manuals(targets)
        print("\n✅ Egyptian automotive targets ingestion completed!")
    except Exception as e:
        print(f"\n❌ Ingestion failed: {e}")
    finally:
        await ingester.close()


if __name__ == "__main__":
    asyncio.run(main())
