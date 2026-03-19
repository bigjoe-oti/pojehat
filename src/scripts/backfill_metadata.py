import asyncio
import logging
import re
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

# Rule-based mapping for domain_tag
TAG_RULES = [
    (re.compile(r"dtc|obd|fault|code|wd|ewd|pinout|wiring|diagram", re.I), "protocol"),
    (re.compile(r"manual|service|repair|workshop|om|instruction|guide", re.I), "vehicle_manual"),
    (re.compile(r"ev|hybrid|hv|battery|electric|phev", re.I), "hv_ev"),
    (re.compile(r"spec|technical|data|brief|bulletin|update", re.I), "general"),
    (re.compile(r"ecu|module|canbus|communication", re.I), "protocol"),
]

async def backfill():
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection = "pojehat_hybrid_v1"
    
    logger.info(f"Starting backfill for {collection}...")
    
    # Scroll through all points
    next_page_offset = None
    processed = 0
    updated = 0
    
    while True:
        result, next_page_offset = await client.scroll(
            collection_name=collection,
            limit=100,
            with_payload=True,
            with_vectors=False,
            offset=next_page_offset
        )
        
        for point in result:
            processed += 1
            payload = point.payload
            current_tag = payload.get("domain_tag")
            file_name = payload.get("file_name", "") or ""
            source = payload.get("source", "") or ""
            
            # Only update if UNTAGGED or missing or internal generic marker
            if not current_tag or current_tag in ["UNTAGGED", "MISSING", "UNKNOWN"]:
                new_tag = "general" # Default fallback
                
                # Check rules
                search_str = f"{file_name} {source}"
                matched = False
                for pattern, tag in TAG_RULES:
                    if pattern.search(search_str):
                        new_tag = tag
                        matched = True
                        break
                
                # Update point
                await client.set_payload(
                    collection_name=collection,
                    payload={"domain_tag": new_tag},
                    points=[point.id]
                )
                updated += 1
        
        if not next_page_offset:
            break
        
        if processed % 500 == 0:
            logger.info(f"Processed {processed} points, updated {updated}...")

    await client.close()
    logger.info(f"Backfill complete. Total processed: {processed}, Total updated: {updated}")

if __name__ == "__main__":
    asyncio.run(backfill())
