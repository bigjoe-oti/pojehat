"""
Pydantic schemas for the Pojehat API layer.
"""

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class DiagnosticQuery(BaseModel):
    """
    Schema for vehicle diagnostic questions.
    """

    query: str = Field(..., description="The diagnostic question from the user")
    vehicle_context: str = Field(
        "", description="Vehicle details (VIN, Model, Year, etc.)"
    )
    conversation_id: str | None = None  # Client generates UUID per session
    history: list[ConversationMessage] = Field(
        default_factory=list,
        max_length=10,  # Hard cap — prevent context stuffing
        description="Recent conversation history, oldest first. Max 10 turns.",
    )


class DiagnosticResponse(BaseModel):
    """
    Schema for AI-technician diagnostic responses.
    """

    response: str = Field(..., description="The AI-technician's response")


class VINDecodeResponse(BaseModel):
    vin: str
    valid: bool
    make: str = ""
    model_year: str = ""
    wmi: str = ""
    country: str = ""
    vehicle_context_suggestion: str = ""
    message: str = ""
    confidence: str = ""  # "high" | "medium" | "low"
    technical_brief: str = ""  # Instant HTML/Markdown technical brief
    has_rag_followup: bool = False  # True if spec was found (trigger Bubble 2)
    # ── Pojehat Enrichment Layer (Legacy) ──────────────────────────────────
    ecu_family: str = ""  # e.g. "Bosch ME17.9.11"
    transmission_code: str = ""  # e.g. "Jatco JF015E CVT7 / RE0F11A"
    engine_code: str = ""  # e.g. "HR15DE 1.5L DOHC 16V"
    known_issues: list[str] = []  # Top known failure patterns for this platform
    special_functions_hint: str = ""  # Recommended special functions / resets


class VINRagRequest(BaseModel):
    vehicle_context: str
    vin: str


class VINRagResponse(BaseModel):
    content: str


class IngestionResponse(BaseModel):
    status: str
    message: str
    filename: str | None = None


class WebIngestionRequest(BaseModel):
    """
    Schema for web-based manual ingestion.
    """

    url: str = Field(..., description="The URL of the manual or model page")
    vehicle_context: str = Field(..., description="Vehicle context for the manual")
