"""
Pydantic schemas for the Pojehat API layer.
"""

from pydantic import BaseModel, Field


class DiagnosticQuery(BaseModel):
    """
    Schema for vehicle diagnostic questions.
    """

    query: str = Field(..., description="The diagnostic question from the user")
    vehicle_context: str = Field(
        ..., description="Vehicle details (VIN, Model, Year, etc.)"
    )


class DiagnosticResponse(BaseModel):
    """
    Schema for AI-technician diagnostic responses.
    """

    response: str = Field(..., description="The AI-technician's response")


class IngestionResponse(BaseModel):
    """
    Schema for document ingestion status.
    """

    status: str = Field(
        ..., description="Status of the ingestion (e.g., success, pending)"
    )
    message: str = Field(..., description="Human-readable message")
    filename: str | None = Field(
        default=None, description="The name of the uploaded/downloaded file"
    )


class WebIngestionRequest(BaseModel):
    """
    Schema for web-based manual ingestion.
    """

    url: str = Field(..., description="The URL of the manual or model page")
    vehicle_context: str = Field(..., description="Vehicle context for the manual")
