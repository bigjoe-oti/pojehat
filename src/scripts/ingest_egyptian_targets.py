"""
Bulk ingestion script for Egyptian automotive targets.
Extracts actual PDF/image URLs from Google search links and ingests them.
"""

import asyncio
import re
from typing import Dict, List

from src.services.bulk_ingester import BulkIngester


def extract_actual_url(google_url: str) -> str:
    """
    Extract actual PDF/image URL from Google search URL.
    Example: https://www.google.com/search?q=https://carmanualshub.com/...pdf
    -> https://carmanualshub.com/...pdf
    """
    # Simple extraction - look for http(s) after q=
    match = re.search(r'q=(https?://[^&]+)', google_url)
    if match:
        return match.group(1)
    # If no match, return original (might already be direct URL)
    return google_url


# Egyptian automotive targets grouped by brand
EGYPTIAN_TARGETS = [
    # NISSAN - N17 Sunny (Egypt's #1 car) and J11/J12 Qashqai
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Nissan-Sunny-Wiring-Diagrams.pdf",
        "context": "Nissan Sunny N17 Wiring Diagrams",
        "brand": "Nissan",
        "model": "Sunny N17",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Nissan-Sentra-Wiring-Diagrams.pdf",
        "context": "Nissan Sentra Wiring Diagrams",
        "brand": "Nissan",
        "model": "Sentra",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Nissan-Qashqai-Wiring-Diagrams.pdf",
        "context": "Nissan Qashqai J11/J12 Wiring Diagrams",
        "brand": "Nissan",
        "model": "Qashqai J11/J12",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-NissanSunny-N17-block-kapot.jpg",
        "context": "Nissan Sunny N17 Fuse Box Diagram",
        "brand": "Nissan",
        "model": "Sunny N17",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-NissanQashqai-J11-block-kapot.jpg",
        "context": "Nissan Qashqai J11 Fuse Box Diagram",
        "brand": "Nissan",
        "model": "Qashqai J11",
        "doc_type": "fuse_diagram",
    },
    # KIA - YD/BD Cerato and QL Sportage electricals
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Kia-Cerato-Wiring-Diagrams.pdf",
        "context": "Kia Cerato YD/BD Wiring Diagrams",
        "brand": "Kia",
        "model": "Cerato YD/BD",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Kia-Sportage-Wiring-Diagrams.pdf",
        "context": "Kia Sportage QL Wiring Diagrams",
        "brand": "Kia",
        "model": "Sportage QL",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/04/EN-KiaCerato-YD-block-kapot.jpg",
        "context": "Kia Cerato YD Fuse Box Diagram",
        "brand": "Kia",
        "model": "Cerato YD",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/02/EN-KiaSportage4-block-kapot.jpg",
        "context": "Kia Sportage 4 Fuse Box Diagram",
        "brand": "Kia",
        "model": "Sportage 4",
        "doc_type": "fuse_diagram",
    },
    # CHEVROLET - Cruze, Optra
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Chevrolet-Cruze-Wiring-Diagrams.pdf",
        "context": "Chevrolet Cruze Wiring Diagrams",
        "brand": "Chevrolet",
        "model": "Cruze",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Chevrolet-Optra-Wiring-Diagrams.pdf",
        "context": "Chevrolet Optra Wiring Diagrams",
        "brand": "Chevrolet",
        "model": "Optra",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-ChevroletCruze-block-kapot.jpg",
        "context": "Chevrolet Cruze Fuse Box Diagram",
        "brand": "Chevrolet",
        "model": "Cruze",
        "doc_type": "fuse_diagram",
    },
    # RENAULT - Logan, Sandero
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Renault-Logan-Wiring-Diagrams.pdf",
        "context": "Renault Logan Wiring Diagrams",
        "brand": "Renault",
        "model": "Logan",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-RenaultLogan2-block-kapot.jpg",
        "context": "Renault Logan 2 Fuse Box Diagram",
        "brand": "Renault",
        "model": "Logan 2",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-RenaultSandero2-block-kapot.jpg",
        "context": "Renault Sandero 2 Fuse Box Diagram",
        "brand": "Renault",
        "model": "Sandero 2",
        "doc_type": "fuse_diagram",
    },
    # TOYOTA - Corolla E150/E170
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Toyota-Corolla-Wiring-Diagrams.pdf",
        "context": "Toyota Corolla Wiring Diagrams",
        "brand": "Toyota",
        "model": "Corolla",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/03/EN-ToyotaCorolla-E150-block-kapot.jpg",
        "context": "Toyota Corolla E150 Fuse Box Diagram",
        "brand": "Toyota",
        "model": "Corolla E150",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/11/EN-ToyotaCorolla-E170-block-kapot.jpg",
        "context": "Toyota Corolla E170 Fuse Box Diagram",
        "brand": "Toyota",
        "model": "Corolla E170",
        "doc_type": "fuse_diagram",
    },
    # MITSUBISHI - Lancer Shark
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/08/Mitsubishi-Lancer-Wiring-Diagrams.pdf",
        "context": "Mitsubishi Lancer Wiring Diagrams",
        "brand": "Mitsubishi",
        "model": "Lancer",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/03/EN-MitsubishiLancer10-block-kapot.jpg",
        "context": "Mitsubishi Lancer 10 Fuse Box Diagram",
        "brand": "Mitsubishi",
        "model": "Lancer 10",
        "doc_type": "fuse_diagram",
    },
    # CHERY - Tiggo, Arrizo
    {
        "url": "https://www.google.com/search?q=https://www.cheryinternational.com/service/manual/Tiggo7_Maintenance_Manual.pdf",
        "context": "Chery Tiggo 7 Maintenance Manual",
        "brand": "Chery",
        "model": "Tiggo 7",
        "doc_type": "maintenance_manual",
    },
    {
        "url": "https://www.google.com/search?q=https://www.cheryinternational.com/service/manual/Tiggo8Pro_EWD_EN.pdf",
        "context": "Chery Tiggo 8 Pro Electrical Wiring Diagram",
        "brand": "Chery",
        "model": "Tiggo 8 Pro",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/11/CheryArrizo7-block-kapot-1.jpg",
        "context": "Chery Arrizo 7 Fuse Box Diagram",
        "brand": "Chery",
        "model": "Arrizo 7",
        "doc_type": "fuse_diagram",
    },
    # MG - 5, ZS
    {
        "url": "https://www.google.com/search?q=https://mgworkshopmanual.com/mg5-ewd.pdf",
        "context": "MG 5 Electrical Wiring Diagram",
        "brand": "MG",
        "model": "MG5",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://mgworkshopmanual.com/mgzs-wiring.pdf",
        "context": "MG ZS Wiring Diagram",
        "brand": "MG",
        "model": "ZS",
        "doc_type": "wiring_diagram",
    },
    # VAG GROUP - Skoda Octavia, VW Passat
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Skoda-Octavia-Wiring-Diagrams.pdf",
        "context": "Skoda Octavia Wiring Diagrams",
        "brand": "Skoda",
        "model": "Octavia",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Volkswagen-Passat-Wiring-Diagrams.pdf",
        "context": "Volkswagen Passat Wiring Diagrams",
        "brand": "Volkswagen",
        "model": "Passat",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/05/EN-VWPassatB8-block-kapot.jpg",
        "context": "Volkswagen Passat B8 Fuse Box Diagram",
        "brand": "Volkswagen",
        "model": "Passat B8",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/12/EN-SkodaOctavia3-block-kapot.jpg",
        "context": "Skoda Octavia 3 Fuse Box Diagram",
        "brand": "Skoda",
        "model": "Octavia 3",
        "doc_type": "fuse_diagram",
    },
    # OPEL - Astra
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Opel-Astra-Wiring-Diagrams.pdf",
        "context": "Opel Astra Wiring Diagrams",
        "brand": "Opel",
        "model": "Astra",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-OpelAstraJ-block-kapot.jpg",
        "context": "Opel Astra J Fuse Box Diagram",
        "brand": "Opel",
        "model": "Astra J",
        "doc_type": "fuse_diagram",
    },
    # PEUGEOT / FIAT - 301, Tipo
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Peugeot-301-Wiring-Diagrams.pdf",
        "context": "Peugeot 301 Wiring Diagrams",
        "brand": "Peugeot",
        "model": "301",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/04/EN-FiatTipo-block-kapot.jpg",
        "context": "Fiat Tipo Fuse Box Diagram",
        "brand": "Fiat",
        "model": "Tipo",
        "doc_type": "fuse_diagram",
    },
    # BMW / MERCEDES - E90, W204
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/BMW-3-Series-Service-Manuals.pdf",
        "context": "BMW 3 Series Service Manuals",
        "brand": "BMW",
        "model": "3 Series",
        "doc_type": "service_manual",
    },
    {
        "url": "https://www.google.com/search?q=https://carmanualshub.com/wp-content/uploads/2018/12/Mercedes-Benz-C-Class-Wiring-Diagrams.pdf",
        "context": "Mercedes-Benz C-Class Wiring Diagrams",
        "brand": "Mercedes-Benz",
        "model": "C-Class",
        "doc_type": "wiring_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/01/EN-MercedesW204-block-kapot.jpg",
        "context": "Mercedes W204 Fuse Box Diagram",
        "brand": "Mercedes-Benz",
        "model": "W204",
        "doc_type": "fuse_diagram",
    },
    {
        "url": "https://www.google.com/search?q=https://fusesdiagram.com/wp-content/uploads/2017/11/EN-BMWE90-block-kapot.jpg",
        "context": "BMW E90 Fuse Box Diagram",
        "brand": "BMW",
        "model": "E90",
        "doc_type": "fuse_diagram",
    },
    # ECU HARDWARE SPECIFICS
    {
        "url": "https://www.google.com/search?q=https://ecu-connections.com/wp-content/uploads/2022/bosch-me17-pinout.pdf",
        "context": "Bosch ME17 ECU Pinout",
        "brand": "Bosch",
        "model": "ME17",
        "doc_type": "ecu_pinout",
    },
    {
        "url": "https://www.google.com/search?q=https://vignette.wikia.nocookie.net/external-ecu-pinouts/images/6/6a/Hyundai_ME17.9.11.png",
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
        targets.append({
            "url": actual_url,
            "context": target["context"],
        })
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