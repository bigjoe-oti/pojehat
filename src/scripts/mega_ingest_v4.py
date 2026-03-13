"""
Mega-Ingestion V4: Intelligence Expansion.
Orchestrates deep crawling of premium sources (charm.li, manualslib) using Jina Reader.
Targets high-fidelity technical points for valid models through 2013-2014.
"""

import asyncio
import logging
from src.services.web_ingester import web_ingester

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MEGA_DATA_V4 = [
    # 1. Honda
    {
        "url": "https://charm.li/Honda/2010/Civic%20L4-1.8L/Repair%20and%20Diagnosis/",
        "context": "Honda Civic (2010) Workshop Manual"
    },
    {
        "url": "https://charm.li/Honda/2013/Accord%20L4-2.4L/Repair%20and%20Diagnosis/",
        "context": "Honda Accord (2013) Technical Guidance"
    },

    # 2. Mazda
    {
        "url": "https://charm.li/Mazda/2013/3%20L4-2.0L%20%28MZR%29/Repair%20and%20Diagnosis/",
        "context": "Mazda 3 (2013) ESM/EWD"
    },
    {
        "url": "https://charm.li/Mazda/2013/6%20L4-2.5L/Repair%20and%20Diagnosis/",
        "context": "Mazda 6 (2013) Service Data"
    },

    # 3. Ford (Capped at 2013 on Charm.li)
    {
        "url": "https://charm.li/Ford/2013/Focus%20L4-2.0L/Repair%20and%20Diagnosis/",
        "context": "Ford Focus (2013) Electronic Service Manual"
    },

    # 4. Volvo (Capped at 2013 on Charm.li)
    {
        "url": "https://charm.li/Volvo/2013/XC90%20AWD%20L6-3.2L%20%28B6324S5%29/Repair%20and%20Diagnosis/",
        "context": "Volvo XC90 (2013) Advanced Diagnostics"
    },

    # 5. Suzuki (Kizashi used as high-detail Swift-era proxy)
    {
        "url": "https://charm.li/Suzuki/2010/Kizashi%20AWD%20L4-2.4L/Repair%20and%20Diagnosis/",
        "context": "Suzuki Kizashi (2010) Wiring & Repair"
    },

    # 6. Subaru (Valid 2014 Link)
    {
        "url": "https://charm.li/Subaru/2014/Forester%20F4-2.5L%20DOHC/Repair%20and%20Diagnosis/",
        "context": "Subaru Forester (2014) Boxer Engine ESM"
    },

    # 7. Jeep / Dodge (Capped at 2013)
    {
        "url": "https://charm.li/Jeep/2013/Grand%20Cherokee%204WD%20V6-3.6L/Repair%20and%20Diagnosis/",
        "context": "Jeep Grand Cherokee (2013) Logic"
    },
    {
        "url": "https://charm.li/Dodge%20and%20Ram/2013/Ram%201500%20Truck%204WD%20V8-5.7L/Repair%20and%20Diagnosis/",
        "context": "Dodge Ram 1500 (2013) hemi Wiring"
    },

    # --- Phase 3: Regional Expansion Batch ---
    # Renault
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Renault-Logan-Wiring-Diagrams.pdf", "context": "Renault Logan Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/01/EN-RenaultLogan2-block-kapot.jpg", "context": "Renault Logan 2 Fuse Block"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/01/EN-RenaultSandero2-block-kapot.jpg", "context": "Renault Sandero 2 Fuse Block"},
    
    # Toyota
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/08/Toyota-Corolla-Wiring-Diagrams.pdf", "context": "Toyota Corolla Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/03/EN-ToyotaCorolla-E150-block-kapot.jpg", "context": "Toyota Corolla E150 Fuses"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/11/EN-ToyotaCorolla-E170-block-kapot.jpg", "context": "Toyota Corolla E170 Fuses"},
    
    # Mitsubishi
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/08/Mitsubishi-Lancer-Wiring-Diagrams.pdf", "context": "Mitsubishi Lancer Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/03/EN-MitsubishiLancer10-block-kapot.jpg", "context": "Mitsubishi Lancer 10 Fuses"},
    
    # Chery
    {"url": "https://www.cheryinternational.com/service/manual/Tiggo7_Maintenance_Manual.pdf", "context": "Chery Tiggo 7 Manual"},
    {"url": "https://www.cheryinternational.com/service/manual/Tiggo8Pro_EWD_EN.pdf", "context": "Chery Tiggo 8 Pro EWD"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/11/CheryArrizo7-block-kapot-1.jpg", "context": "Chery Arrizo 7 Fuses"},
    
    # MG
    {"url": "https://mgworkshopmanual.com/mg5-ewd.pdf", "context": "MG5 EWD"},
    {"url": "https://mgworkshopmanual.com/mgzs-wiring.pdf", "context": "MG ZS Wiring"},
    
    # VAG
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Skoda-Octavia-Wiring-Diagrams.pdf", "context": "Skoda Octavia Wiring"},
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Volkswagen-Passat-Wiring-Diagrams.pdf", "context": "VW Passat Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/05/EN-VWPassatB8-block-kapot.jpg", "context": "VW Passat B8 Fuses"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/12/EN-SkodaOctavia3-block-kapot.jpg", "context": "Skoda Octavia 3 Fuses"},
    
    # Opel
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Opel-Astra-Wiring-Diagrams.pdf", "context": "Opel Astra Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/01/EN-OpelAstraJ-block-kapot.jpg", "context": "Opel Astra J Fuses"},
    
    # Peugeot / Fiat
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Peugeot-301-Wiring-Diagrams.pdf", "context": "Peugeot 301 Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/04/EN-FiatTipo-block-kapot.jpg", "context": "Fiat Tipo Fuses"},
    
    # BMW / Mercedes
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/BMW-3-Series-Service-Manuals.pdf", "context": "BMW 3 Series Manual"},
    {"url": "https://carmanualshub.com/wp-content/uploads/2018/12/Mercedes-Benz-C-Class-Wiring-Diagrams.pdf", "context": "Mercedes C-Class Wiring"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/01/EN-MercedesW204-block-kapot.jpg", "context": "Mercedes W204 Fuses"},
    {"url": "https://fusesdiagram.com/wp-content/uploads/2017/11/EN-BMWE90-block-kapot.jpg", "context": "BMW E90 Fuses"},
    
    # ECU Hardware
    {"url": "https://ecu-connections.com/wp-content/uploads/2022/bosch-me17-pinout.pdf", "context": "Bosch ME17 Pinout"},
    {"url": "https://vignette.wikia.nocookie.net/external-ecu-pinouts/images/6/6a/Hyundai_ME17.9.11.png", "context": "Hyundai ME17.9.11 Pinout"}
]

async def run_mega_ingest_v4():
    """Execute the Expansion Phase Batch Ingestion."""
    logger.info(f"🚀 Launching Regional Expansion (V4) for {len(MEGA_DATA_V4)} targets...")
    
    for item in MEGA_DATA_V4:
        url = item["url"]
        context = item["context"]
        
        # Clean URL if it's a google search wrapper
        if "google.com/search?q=" in url:
            url = url.split("google.com/search?q=")[-1].split("&")[0]
            url = url.replace("%3A", ":").replace("%2F", "/")
            
        logger.info(f"⏳ Expansion Target: {context}")
        logger.info(f"🔗 URL: {url}")
        try:
            await web_ingester.process_url(url, context)
            logger.info(f"✅ Ingestion Successful: {context}")
        except Exception as e:
            logger.error(f"❌ Ingestion Failed: {context} | Error: {str(e)}")
            continue
            
    logger.info("🏁 Expansion Phase Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(run_mega_ingest_v4())
