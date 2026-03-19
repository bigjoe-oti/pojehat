import asyncio
import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchText
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_tags")

async def fix_tags():
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection = "pojehat_obd_ecu_v1"
    
    logger.info(f"Scanning {collection} for incorrect domain_tags...")
    
    # Target 1: hv_ev -> sensors_specs or ecu_pinout
    # We'll just reset them all to UNTAGGED first or use a safer default
    # The user says "hv_ev and protocol — both wrong".
    
    target_tags = ["hv_ev", "protocol"]
    
    for tag in target_tags:
        logger.info(f"Fixing tag: {tag}")
        next_page = None
        while True:
            points, next_page = await client.scroll(
                collection_name=collection,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="domain_tag", match=MatchValue(value=tag))
                    ]
                ),
                limit=100,
                with_payload=True,
                offset=next_page
            )
            
            if not points:
                break
                
            for point in points:
                # Intelligent re-tagging based on vehicle_context/source
                ctx = (point.payload.get("vehicle_context") or "").lower()
                source = (point.payload.get("source") or "").lower()
                
                new_tag = "ecu_pinout" # Default for obd_ecu collection
                if "dtc" in ctx or "fault" in ctx or "code" in ctx:
                    new_tag = "dtc_database"
                elif "sensor" in ctx or "spec" in ctx or "voltage" in ctx:
                    new_tag = "sensor_specs"
                elif "hv" in ctx or "battery" in ctx:
                    # In obd_ecu, HV is likely High Voltage sensor/circuit, not vehicle type
                    new_tag = "sensor_specs"
                
                await client.set_payload(
                    collection_name=collection,
                    payload={"domain_tag": new_tag},
                    points=[point.id]
                )
            
            if not next_page:
                break
                
    await client.close()
    logger.info("Tag correction complete.")

if __name__ == "__main__":
    asyncio.run(fix_tags())
