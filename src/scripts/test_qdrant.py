import asyncio

from qdrant_client import AsyncQdrantClient

from src.core.config import settings


async def check():
    client = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    colls = await client.get_collections()
    for coll in colls.collections:
        info = await client.get_collection(coll.name)
        print(f"Collection: {coll.name} | Points: {info.points_count}")


if __name__ == "__main__":
    asyncio.run(check())
