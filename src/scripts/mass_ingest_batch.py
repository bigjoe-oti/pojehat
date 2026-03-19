import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from llama_index.core import Settings
from llama_index.embeddings.openai import OpenAIEmbedding

from src.core.config import settings
from src.domain.pdf_parser import ingest_manual


async def main():
    # Force global settings to match config
    Settings.embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
        dimensions=1536,
    )

    pdf_dir = Path("/Users/OTI_1/Desktop/pojehat/pdfs")
    pdf_files = [f for f in pdf_dir.glob("*.pdf")]

    print(f"Found {len(pdf_files)} PDF files to ingest.")

    for pdf_path in pdf_files:
        print(f"--- Processing: {pdf_path.name} ---")
        try:
            result = await ingest_manual(str(pdf_path), vehicle_context="General Automotive Technical Data")
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
