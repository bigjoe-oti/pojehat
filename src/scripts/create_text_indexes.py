"""
One-time migration: add text indexes to vehicle_context and file_name
on both Qdrant collections.

WHY: _parse_vehicle_filter uses MatchText for partial token matching
(e.g. "Sunny" matching "Nissan Sunny B17 (HR15DE / JF015E CVT7)").
MatchText requires a TEXT index. The existing keyword index is
insufficient. Strict mode returns 400 without the correct index type.

SAFE TO RE-RUN: Qdrant create_payload_index is idempotent.
"""
import asyncio
import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import TextIndexParams, TokenizerType
from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLLECTIONS = ["pojehat_hybrid_v1", "pojehat_obd_ecu_v1"]
TEXT_FIELDS = ["vehicle_context", "file_name"]


async def main() -> None:
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )

    for collection in COLLECTIONS:
        for field in TEXT_FIELDS:
            logger.info(
                "Creating text index: collection=%s field=%s",
                collection, field
            )
            try:
                await client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=TextIndexParams(
                        type="text",
                        tokenizer=TokenizerType.WORD,
                        min_token_len=2,
                        lowercase=True,
                    ),
                )
                logger.info("  ✓ Created text index: %s.%s", collection, field)
            except Exception as e:
                # If index already exists Qdrant may raise — log and continue
                logger.warning(
                    "  ⚠ Index creation warning for %s.%s: %s",
                    collection, field, e
                )

    # Verify indexes were created
    logger.info("\n=== VERIFICATION ===")
    for collection in COLLECTIONS:
        info = await client.get_collection(collection)
        schema = info.payload_schema or {}
        for field in TEXT_FIELDS:
            field_info = schema.get(field)
            logger.info(
                "  %s.%s → %s",
                collection, field,
                field_info.data_type if field_info else "NOT FOUND"
            )

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
