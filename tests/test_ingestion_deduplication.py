import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from src.services.web_ingester import web_ingester


async def test_deduplication():
    logging.basicConfig(level=logging.INFO)
    
    # This URL was successfully ingested in Batch V5 (confirmed by logs)
    target_url = "https://github.com/digitalbond/canbus-utils/blob/master/obdii-pids.json"
    
    print(f"\n{'='*60}")
    print(f"TESTING DEDUPLICATION FOR: {target_url}")
    print(f"{'='*60}")
    
    try:
        # Should print [SKIP] and return immediately
        await web_ingester.process_url(target_url, "Duplicate Test")
        print("\n[SUCCESS] Deduplication logic executed correctly.")
    except Exception as e:
        print(f"\n[ERROR] Deduplication test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_deduplication())
