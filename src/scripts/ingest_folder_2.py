import asyncio
import logging
import sys
from pathlib import Path

from src.domain.pdf_parser import ingest_manual

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    stream=sys.stdout,
)
logger = logging.getLogger('ingest_folder_2')

# Folder 2 path
FOLDER_PATH = Path("/Users/OTI_1/Desktop/pojehat/pdfs/2")

async def main():
    if not FOLDER_PATH.exists():
        logger.error(f"Directory {FOLDER_PATH} does not exist")
        return

    pdf_files = sorted(list(FOLDER_PATH.glob("*.pdf")))
    logger.info(f"Found {len(pdf_files)} PDF files in {FOLDER_PATH}")

    ok, fail = 0, 0
    for i, pdf_path in enumerate(pdf_files, 1):
        filename = pdf_path.name
        logger.info(f">>> [{i}/{len(pdf_files)}] Processing: {filename}")
        try:
            # We use the filename without extension as context
            context = f"Local Document Ingestion - Folder 2: {pdf_path.stem.replace('_', ' ')}"
            await ingest_manual(str(pdf_path), vehicle_context=context)
            logger.info(f"SUCCESS [{i}/{len(pdf_files)}]: {filename}")
            ok += 1
        except Exception as e:
            logger.error(f"FAILED [{i}/{len(pdf_files)}]: {filename} | Error: {str(e)}")
            fail += 1

    logger.info(f"=== Ingestion Folder 2 complete: {ok} ok / {fail} failed ===")

if __name__ == "__main__":
    asyncio.run(main())
