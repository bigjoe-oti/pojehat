import asyncio
import logging
import sys
from pathlib import Path

from src.domain.pdf_parser import ingest_manual

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

PDF_DIR = Path("/Users/OTI_1/Desktop/pojehat/pdfs")

async def main():
    if not PDF_DIR.exists() or not PDF_DIR.is_dir():
        logger.error(f"Directory {PDF_DIR} does not exist.")
        sys.exit(1)

    pdf_files = list(PDF_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"No PDF files found in {PDF_DIR}.")
        sys.exit(0)

    logger.info(f"Found {len(pdf_files)} PDF files. Starting bulk ingestion...")

    success_count = 0
    fail_count = 0

    for pdf_path in pdf_files:
        logger.info(f"[*] Processing: {pdf_path.name}")
        try:
            # Use the stem of the file as context if unavailable
            context = pdf_path.stem.replace("_", " ")
            result = await ingest_manual(str(pdf_path), vehicle_context=context)

            if result.get("status") == "success":
                logger.info(
                    f"[+] Successfully ingested {pdf_path.name} "
                    f"({result.get('pages_processed', 0)} pages)."
                )
                success_count += 1
            else:
                logger.warning(
                    f"[-] Failed to ingest {pdf_path.name}: {result.get('message')}"
                )
                fail_count += 1

        except Exception as e:
            logger.error(f"[!] Error processing {pdf_path.name}: {e}")
            fail_count += 1

    logger.info(
        f"Bulk ingestion complete. Success: {success_count}, Failed: {fail_count}"
    )

if __name__ == "__main__":
    asyncio.run(main())
