"""
OEM Automotive PDF parser and ingestion module for Pojehat.
"""

from pathlib import Path

import fitz  # PyMuPDF
from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import TokenTextSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore

from src.core.config import settings

# Global configuration for rich technical metadata
Settings.chunk_size = 4096
Settings.chunk_overlap = 200


async def ingest_manual(
    file_path: str, 
    vehicle_context: str = "Unknown"
) -> dict[str, str | int]:
    """
    Extracts data from OEM automotive PDFs or Images and pushes to Qdrant.
    Creates page-level or item-level documents for granular retrieval.
    """
    doc_path = Path(file_path)
    output_image_dir = Path(settings.IMAGE_STORAGE_PATH)
    output_image_dir.mkdir(parents=True, exist_ok=True)
    
    documents = []
    total_pages = 0

    if doc_path.suffix.lower() == ".pdf":
        pdf_document = fitz.open(file_path)
        total_pages = len(pdf_document)

        for page_num in range(total_pages):
            page = pdf_document[page_num]
            page_text = page.get_text()
            
            # Extract images for this page
            page_image_paths = []
            for img_index, img in enumerate(page.get_images()):
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                image_filename = f"{doc_path.stem}_p{page_num}_i{img_index}.{image_ext}"
                image_save_path = output_image_dir / image_filename

                with open(image_save_path, "wb") as f:
                    f.write(image_bytes)
                page_image_paths.append(str(image_save_path))

            # Create document with rich metadata
            metadata = {
                "file_name": doc_path.name,
                "page_num": page_num + 1,
                "total_pages": total_pages,
                "vehicle_context": vehicle_context,
                "image_paths": page_image_paths,
                "source_type": "pdf_manual"
            }
            documents.append(Document(text=page_text, metadata=metadata))
        pdf_document.close()
    
    elif doc_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        total_pages = 1
        # For images, the image itself is the payload
        metadata = {
            "file_name": doc_path.name,
            "page_num": 1,
            "total_pages": 1,
            "vehicle_context": vehicle_context,
            "image_paths": [str(doc_path)],
            "source_type": "schematic_image"
        }
        # In the future, we could add OCR here if needed
        documents.append(
            Document(
                text=f"Schematic/Layout: {doc_path.name} for {vehicle_context}", 
                metadata=metadata
            )
        )

    if not documents:
        return {"status": "error", "message": "No documents extracted"}

    # 2. Index the documents
    index_documents(documents)

    return {
        "status": "success", 
        "pages_processed": total_pages,
        "collection": settings.QDRANT_COLLECTION_NAME
    }


def _get_vector_store_and_index():
    """Helper to setup the embedding model and vector store."""
    embed_model = OpenAIEmbedding(
        model=settings.EMBED_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        api_base="https://openrouter.ai/api/v1",
    )

    from qdrant_client import QdrantClient
    from qdrant_client.http import models

    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    collection_name = settings.QDRANT_COLLECTION_NAME

    # Ensure collection exists
    collections = client.get_collections()
    if not any(c.name == collection_name for c in collections.collections):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,
                distance=models.Distance.COSINE
            ),
            sparse_vectors_config={
                "text-sparse-new": models.SparseVectorParams(
                    index=models.SparseIndexParams(on_disk=True)
                )
            }
        )

    vector_store = QdrantVectorStore(
        collection_name=collection_name,
        client=client,
        enable_hybrid=True,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return embed_model, storage_context


def index_documents(documents: list[Document]):
    """Generic document indexing for Qdrant."""
    if not documents:
        return
    
    embed_model, storage_context = _get_vector_store_and_index()
    
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
        transformations=[TokenTextSplitter(chunk_size=4096, chunk_overlap=200)]
    )
