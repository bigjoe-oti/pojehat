"""
API routes for diagnostics and document ingestion.
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile

from src.app.api.schemas import (
    DiagnosticQuery,
    DiagnosticResponse,
    IngestionResponse,
    WebIngestionRequest,
)
from src.core.config import settings
from src.domain.pdf_parser import ingest_manual
from src.domain.rag_engine import query_mechanic_agent
from src.services.web_ingester import web_ingester

router = APIRouter()

# Ensure upload directory exists
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


@router.post("/diagnostics/ask", response_model=DiagnosticResponse)
async def ask_diagnostics(query: DiagnosticQuery) -> DiagnosticResponse:
    """
    Expert Tier-3 technician endpoint for vehicle diagnostics.
    """
    try:
        response_text = await query_mechanic_agent(
            query=query.query, car_context=query.vehicle_context
        )
        return DiagnosticResponse(response=response_text)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Diagnostic engine failure: {str(e)}"
        ) from e


@router.post("/ingestion/upload", response_model=IngestionResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    vehicle_context: str = Form(...),
    file: UploadFile = File(...),
) -> IngestionResponse:
    """
    Upload OEM PDF manuals for vectorization and indexing.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    upload_path = Path(settings.UPLOAD_DIR) / file.filename

    try:
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"File upload failed: {str(e)}"
        ) from e

    # Offload heavy vectorization to background task
    background_tasks.add_task(ingest_manual, str(upload_path))

    return IngestionResponse(
        status="pending",
        message=(
            f"Ingestion started for {file.filename} with context: "
            f"{vehicle_context}"
        ),
        filename=file.filename,
    )


@router.post("/ingestion/web", response_model=IngestionResponse)
async def upload_from_web(
    background_tasks: BackgroundTasks,
    request: WebIngestionRequest,
) -> IngestionResponse:
    """
    Ingest manuals from a URL (manuals.co or direct PDF).
    """
    # Offload heavy scraping and vectorization to background task
    background_tasks.add_task(
        web_ingester.process_url, request.url, request.vehicle_context
    )

    return IngestionResponse(
        status="pending",
        message=f"Web ingestion started for {request.url}",
    )
