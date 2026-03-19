"""
API routes for diagnostics and document ingestion.
"""

import asyncio
import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from src.app.api.schemas import (
    DiagnosticQuery,
    DiagnosticResponse,
    IngestionResponse,
    VINDecodeResponse,  # Add explicitly to avoid local name shadowing
    VINRagRequest,
    VINRagResponse,
    WebIngestionRequest,
)
from src.core.config import settings
from src.domain.pdf_parser import ingest_manual
from src.domain.rag_engine import query_mechanic_agent
from src.domain.vehicle_specs import (
    apply_enrichment,
    format_vehicle_brief,
    get_spec,
)
from src.services.web_ingester import web_ingester

# ---------------------------------------------------------------------------
# Process-level VIN result cache (LRU, max 500 entries)
# VIN specifications are immutable — caching is always safe.
# Resets on server restart. No external dependency required.
# Protects auto.dev API quota. ~170 bytes per entry = ~85KB max.
# ---------------------------------------------------------------------------
_VIN_CACHE: OrderedDict[str, VINDecodeResponse] = OrderedDict()
_VIN_CACHE_MAX = 500


def _vin_cache_get(vin: str) -> VINDecodeResponse | None:
    if vin in _VIN_CACHE:
        _VIN_CACHE.move_to_end(vin)
        return _VIN_CACHE[vin]
    return None


def _vin_cache_set(vin: str, result: VINDecodeResponse) -> None:
    _VIN_CACHE[vin] = result
    _VIN_CACHE.move_to_end(vin)
    if len(_VIN_CACHE) > _VIN_CACHE_MAX:
        _VIN_CACHE.popitem(last=False)


# ---------------------------------------------------------------------------
# In-process sliding window rate limiter — no Redis, no dependencies
# 20 requests per 60 seconds per IP. Resets on server restart.
# Switch to Redis-backed when running multiple server instances.
# ---------------------------------------------------------------------------
from collections import defaultdict
import time

_RATE_WINDOWS: defaultdict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_REQUESTS: int = 20
_RATE_LIMIT_WINDOW_S: int = 60


def _check_rate_limit(client_ip: str) -> bool:
    """
    Sliding window check. Returns True if allowed, False if limited.
    Prunes expired timestamps on every call — O(n) on window size only.
    """
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW_S
    _RATE_WINDOWS[client_ip] = [t for t in _RATE_WINDOWS[client_ip] if t > cutoff]
    if len(_RATE_WINDOWS[client_ip]) >= _RATE_LIMIT_REQUESTS:
        return False
    _RATE_WINDOWS[client_ip].append(now)
    return True


router = APIRouter()
_log = logging.getLogger(__name__)

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# VIN Decode Models
# ---------------------------------------------------------------------------


class VINDecodeRequest(BaseModel):
    vin: str = Field(..., min_length=17, max_length=17)


# Enrichment delegates to src.domain.vehicle_specs per Rule 2

# ---------------------------------------------------------------------------
# WMI Table  (Egyptian market priority + MENA / Global)
# ---------------------------------------------------------------------------

_WMI_TABLE: dict[str, dict[str, str]] = {
    # Nissan
    "JN1": {"make": "Nissan", "country": "Japan"},
    "JN8": {"make": "Nissan", "country": "Japan"},
    "JNK": {"make": "Nissan/Infiniti", "country": "Japan"},
    "5N1": {"make": "Nissan", "country": "USA"},
    "3N1": {"make": "Nissan", "country": "Mexico"},
    "MNT": {"make": "Nissan", "country": "Egypt/Thailand"},
    # Toyota
    "JT2": {"make": "Toyota", "country": "Japan"},
    "JT3": {"make": "Toyota", "country": "Japan"},
    "JTD": {"make": "Toyota", "country": "Japan"},
    "JTE": {"make": "Toyota", "country": "Japan"},
    "JTF": {"make": "Toyota", "country": "Japan"},
    "MR0": {"make": "Toyota", "country": "Indonesia"},
    "MHF": {"make": "Toyota", "country": "Thailand"},
    "2T1": {"make": "Toyota", "country": "Canada"},
    "4T1": {"make": "Toyota", "country": "USA"},
    "AHT": {"make": "Toyota", "country": "South Africa"},
    # Hyundai
    "KMH": {"make": "Hyundai", "country": "South Korea"},
    "KMF": {"make": "Hyundai", "country": "South Korea"},
    "KME": {"make": "Hyundai", "country": "South Korea"},
    "5NP": {"make": "Hyundai", "country": "USA"},
    "MAL": {"make": "Hyundai", "country": "India"},
    # Kia
    "KNA": {"make": "Kia", "country": "South Korea"},
    "KND": {"make": "Kia", "country": "South Korea"},
    "KNY": {"make": "Kia", "country": "South Korea"},
    "5XX": {"make": "Kia", "country": "USA"},
    # Renault / Dacia
    "VF1": {"make": "Renault", "country": "France"},
    "VF6": {"make": "Renault", "country": "France"},
    "UU1": {"make": "Dacia/Renault", "country": "Romania"},
    "UU2": {"make": "Dacia/Renault", "country": "Romania"},
    # Peugeot / Citroen
    "VF3": {"make": "Peugeot", "country": "France"},
    "VF7": {"make": "Citroen", "country": "France"},
    "VF8": {"make": "Citroen", "country": "France"},
    # Chery
    "LS4": {"make": "Chery", "country": "China"},
    "LS5": {"make": "Chery/Changan", "country": "China"},
    "LS6": {"make": "Changan", "country": "China"},
    "LSY": {"make": "Chery", "country": "China"},
    "LFS": {"make": "Chery", "country": "China"},
    "LHG": {"make": "Chery", "country": "China"},
    "PRH": {"make": "Chery", "country": "Malaysia"},
    # MG / SAIC
    "LSJ": {"make": "MG/SAIC", "country": "China"},
    "LSK": {"make": "MG/SAIC", "country": "China"},
    "LDC": {"make": "MG/SAIC", "country": "China"},
    "LRB": {"make": "MG/SAIC", "country": "China"},
    # BYD — aggressive Egypt expansion 2023–2025
    "LJD": {"make": "BYD", "country": "China"},
    # Great Wall / Haval
    "LGX": {"make": "Great Wall/Haval", "country": "China"},
    "LHB": {"make": "Great Wall/Haval", "country": "China"},
    # Fiat / Alfa Romeo
    "ZAR": {"make": "Alfa Romeo", "country": "Italy"},
    # Ford
    "1FA": {"make": "Ford", "country": "USA"},
    "WF0": {"make": "Ford", "country": "Germany"},
    "AJA": {"make": "Ford", "country": "South Africa"},
    "3FA": {"make": "Ford", "country": "Mexico"},
    # BMW / Mercedes
    "WBA": {"make": "BMW", "country": "Germany"},
    "WBY": {"make": "BMW", "country": "Germany"},
    "WDB": {"make": "Mercedes-Benz", "country": "Germany"},
    "WDD": {"make": "Mercedes-Benz", "country": "Germany"},
    "WDC": {"make": "Mercedes-Benz", "country": "Germany"},
    # Honda
    "JHM": {"make": "Honda", "country": "Japan"},
    "1HG": {"make": "Honda", "country": "USA"},
    "MHR": {"make": "Honda", "country": "Thailand"},
    # Mazda
    "JM1": {"make": "Mazda", "country": "Japan"},
    # Suzuki
    "JS1": {"make": "Suzuki", "country": "Japan"},
    "MA3": {"make": "Suzuki", "country": "India"},
    "MBH": {"make": "Suzuki", "country": "Thailand"},
    # Geely additional WMI (LBV handled above, restore LB2/HJZ)
    "LB2": {"make": "Geely", "country": "China"},
    "HJZ": {"make": "Geely", "country": "China"},
    # Renault (regional)
    "RSM": {"make": "Renault Samsung", "country": "South Korea"},
    "MAT": {"make": "Renault", "country": "India"},
    # Hyundai Motor Egypt (HME) — Abu Rawash Assembly
    "PEA": {"make": "Hyundai", "country": "Egypt (HME Assembly)"},
    "PEH": {"make": "Hyundai", "country": "Egypt (HME Assembly)"},
    "PEL": {"make": "Hyundai", "country": "Egypt (HME Assembly)"},
    "PEX": {"make": "Hyundai", "country": "Egypt (HME Assembly)"},
}

_MODEL_YEAR_MAP: dict[str, str] = {
    "A": "2010",
    "B": "2011",
    "C": "2012",
    "D": "2013",
    "E": "2014",
    "F": "2015",
    "G": "2016",
    "H": "2017",
    "J": "2018",
    "K": "2019",
    "L": "2020",
    "M": "2021",
    "N": "2022",
    "P": "2023",
    "R": "2024",
    "S": "2025",
    "T": "2026",
    "V": "2027",  # V reused: also = 1997 in old ISO cycle
    "1": "2001",
    "2": "2002",
    "3": "2003",
    "4": "2004",
    "5": "2005",
    "6": "2006",
    "7": "2007",
    "8": "2008",
    "9": "2009",
    "Y": "2000",
    "X": "1999",
    "W": "1998",
}


# ---------------------------------------------------------------------------
# VIN Helpers
# ---------------------------------------------------------------------------


def _validate_vin_check_digit(vin: str) -> bool:
    """ISO 3779 check digit validation (VIN position 9)."""
    transliteration: dict[str, int] = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "E": 5,
        "F": 6,
        "G": 7,
        "H": 8,
        "J": 1,
        "K": 2,
        "L": 3,
        "M": 4,
        "N": 5,
        "P": 7,
        "R": 9,
        "S": 2,
        "T": 3,
        "U": 4,
        "V": 5,
        "W": 6,
        "X": 7,
        "Y": 8,
        "Z": 9,
    }
    weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
    total = sum(
        (int(c) if c.isdigit() else transliteration.get(c, 0)) * weights[i]
        for i, c in enumerate(vin.upper())
    )
    remainder = total % 11
    check = "X" if remainder == 10 else str(remainder)
    return vin[8].upper() == check


# Enrichment delegates to src.domain.vehicle_specs per Rule 2
# ---------------------------------------------------------------------------
# Context Suggestion Engine — dict-based, model-aware
# ---------------------------------------------------------------------------

# Make-level baseline context strings (used when no model keyword matches)
_CONTEXT_MAKE_MAP: dict[str, str] = {
    "nissan": "Nissan Sunny B17 (HR15DE / JF015E CVT7)",
    "infiniti": "Nissan/Infiniti (VQ35DE / RE7R01A 7AT)",
    "toyota": "Toyota Corolla E210 (M20A-FKS / 6AT)",
    "hyundai": "Hyundai Accent RB (G4FC / A4CF1)",
    "kia": "Kia Cerato BD (G4FG / A6LF1)",
    "chery": "Chery Tiggo 7 (SQRF4J15C / DCT430)",
    "mg": "MG ZS (NSE 1.5L / CVT)",
    "saic": "MG ZS (NSE 1.5L / CVT)",
    "renault": "Renault Logan (K7M / K9K / DP0)",
    "dacia": "Renault/Dacia Logan-Duster (K9K / H4M)",
    "peugeot": "Peugeot 301 (EC5 VTi / AL4 / DP0)",
    "citro": "Citroen C-Elysee (EC5 1.6L / AL4)",
    "mitsubishi": "Mitsubishi Lancer EX (4A92 MIVEC / INVECS-III CVT)",
    "chevrolet": "Chevrolet Cruze J300 (Z18XER / 6T40)",
    "daewoo": "Chevrolet Aveo T300 (F14D4 / 81-40LE)",
    "opel": "Opel Astra J (A18XER / AF33)",
    "vauxhall": "Opel/Vauxhall Astra (A18XER)",
    "land rover": "Land Rover Discovery Sport (Ingenium SD4 / 9HP48)",
    "jaguar": "Jaguar XE/XF (Ingenium Ai4 / ZF 8HP)",
    "skoda": "Skoda Octavia A7 (1.6 MPI / DSG)",
    "volkswagen": "Volkswagen Golf/Passat (1.6 MPI / DSG)",
    "audi": "Audi A4/A6 (TFSI / S-tronic)",
    "porsche": "Porsche (PDK / PCM)",
    "bmw": "BMW 3 Series (B48 / ZF 8HP)",
    "mercedes": "Mercedes C-Class (M264 / 9G-Tronic)",
    "geely": "Geely Emgrand (JLY-4G15 / CVT)",
    "byd": "BYD F3/Song (473QE / 6AT/DCT)",
    "great wall": "Haval H6 (GW4C16 / DCT)",
    "haval": "Haval H6 (GW4C16 / DCT)",
    "changan": "Changan CS35/CS55 (JL4G15 / AT)",
    "honda": "Honda Civic/CR-V (L15B7 Earth Dreams / CVT)",
    "mazda": "Mazda 3 (P5-VPS / SkyActiv-Drive 6AT)",
    "suzuki": "Suzuki Swift/Vitara (K14C / Aisin 6AT)",
    "fiat": "Fiat Tipo (E-torQ 1.6L / C514)",
    "ford": "Ford Focus/Fusion (Ecoboost 1.5T / DPS6)",
}

# Model-aware overrides: (model_keywords, context_string)
# Checked before make-level defaults. Order matters — more specific first.
_CONTEXT_MODEL_OVERRIDES: list[tuple[tuple[str, ...], str]] = [
    # Nissan
    (("qashqai", "j11"), "Nissan Qashqai J11 (MR20DD/HRA2DDT / JF016E CVT8)"),
    (("x-trail", "rogue", "t32"), "Nissan X-Trail T32 (MR20DD / JF016E)"),
    (("sentra", "sylphy"), "Nissan Sentra B18 (HR16DE / Xtronic CVT)"),
    # Toyota
    (("camry",), "Toyota Camry XV70 (A25A-FKS / UA80E 8AT)"),
    (("rav4",), "Toyota RAV4 (M20A-FKS / Direct Shift CVT)"),
    (("yaris",), "Toyota Yaris (1NZ-FE / U340E 4AT)"),
    (("fortuner", "hilux"), "Toyota Fortuner/Hilux (2TR-FE / A750F)"),
    (("land cruiser",), "Toyota Land Cruiser (1GR-FE / AB60F 6AT)"),
    # Hyundai
    (("tucson", "tl ", "nx4"), "Hyundai Tucson TL/NX4 (G4FD/G4FJ / 7-DCT)"),
    (("verna", "accent"), "Hyundai Verna/Accent (G4FC/G4FG / A6GF1)"),
    (("elantra",), "Hyundai Elantra CN7 (G4FG / IVT)"),
    (("santa fe",), "Hyundai Santa Fe TM (G4KP 2.5T / 8AT)"),
    (("sonata",), "Hyundai Sonata DN8 (G4KH SmartStream / IVT)"),
    # Kia
    (("sportage",), "Kia Sportage QL/NQ5 (G4FJ Turbo / 7-DCT)"),
    (("picanto",), "Kia Picanto JA (G3LC / 4AT)"),
    # Peugeot
    (("5008", "p87"), "Peugeot 5008 P87 (EP6CDT THP / Aisin EAT8)"),
    (("308", "508"), "Peugeot 308/508 (EP6DT / EAT6)"),
    (("2008",), "Peugeot 2008 (EB2DTS / EAT8)"),
    # Chevrolet
    (("aveo", "t200", "t300"), "Chevrolet Aveo T300 (F14D4 / Aisin 81-40LE)"),
    (("optra", "lacetti", "j200"), "Chevrolet Optra J200 (F16D3 / ZF 4HP16)"),
    (("cruze",), "Chevrolet Cruze J300 (Z18XER / 6T40 Ecotec)"),
    (("captiva",), "Chevrolet Captiva (Z24XE / A6MF1)"),
    # Honda
    (("cr-v", "crv"), "Honda CR-V RW/RD (L15B7 Turbo / CVT Earth Dreams)"),
    (("hr-v", "hrv"), "Honda HR-V RU (L15Z1 / CVT)"),
    (("city",), "Honda City GM6 (L15A7 / CVT)"),
    # Renault Samsung
    (("samsung", "sm5", "sm6"), "Renault Samsung SM5/SM6 (M5Pt 2.0L / CVT)"),
    # BYD
    (("han", "seal"), "BYD Han/Seal EV (Permanent Magnet Motor / e-platform 3.0)"),
    (("atto", "yuan"), "BYD Atto 3 / Yuan Plus EV (BYD e-platform 3.0)"),
    (("song", "tang"), "BYD Song/Tang (473QE / 6DCT / DM-i hybrid)"),
    # Land Rover / Jaguar
    (("evoque",), "Land Rover Evoque L551 (Ingenium Si4 / 9HP48)"),
    (("discovery sport",), "Land Rover Discovery Sport L550 (Ingenium SD4 / 9HP48)"),
    (("defender",), "Land Rover Defender L663 (Ingenium P400e / 8HP76)"),
]


def _build_vehicle_context_suggestion(make: str, year: str, model: str = "") -> str:
    """
    Build the vehicle context string used to seed the RAG retriever.

    Strategy (2-pass, model-aware):
      Pass 1 — Check model hint against _CONTEXT_MODEL_OVERRIDES keywords.
      Pass 2 — Fall back to _CONTEXT_MAKE_MAP keyed by make_lower.
    The model hint comes from auto.dev (Tier 2) or NHTSA (Tier 3) decode data.
    """
    m = make.lower()
    model_lower = model.lower()
    yr = int(year) if year.isdigit() else 0

    # Pass 1: model-aware override (most specific match wins)
    if model_lower:
        for keywords, context_str in _CONTEXT_MODEL_OVERRIDES:
            if any(kw in model_lower for kw in keywords):
                return context_str

    # Pass 2: make-level lookup (year-adjusted for select brands)
    for make_key, base_ctx in _CONTEXT_MAKE_MAP.items():
        if make_key in m:
            # Year adjustments for key makes
            if make_key == "nissan" and yr >= 2020:
                return "Nissan Sunny B18 / Sentra (HR16DE / Xtronic CVT)"
            if make_key == "toyota" and yr >= 2019:
                return "Toyota Corolla E210 Hybrid (2ZR-FXE / eCVT)"
            if make_key == "hyundai" and yr >= 2020:
                return "Hyundai Accent/Verna (G4FG 1.4L / A6GF1 6AT)"
            if make_key == "chery" and yr >= 2021:
                return "Chery Tiggo 7 Pro (SQRF4J15C 1.5T / DCT430)"
            if make_key == "mg" and yr >= 2022:
                return "MG ZS Hybrid (SGE 1.3T / Aisin TF80SC)"
            return base_ctx

    # Ultimate fallback — generic but clearly labelled for downstream handling
    msg = f"{make} {year} — context not in MENA database. Set manually."
    return msg.strip()


# ---------------------------------------------------------------------------
# Diagnostics Endpoints
# ---------------------------------------------------------------------------


@router.post("/diagnostics/ask", response_model=DiagnosticResponse)
async def ask_diagnostics(
    request: Request,
    query: DiagnosticQuery,
) -> DiagnosticResponse:
    """Expert Tier-3 technician endpoint for vehicle diagnostics."""
    # Resolve real client IP — respects reverse proxy headers
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or request.headers.get("x-real-ip", "")
        or getattr(request.client, "host", "unknown")
    )

    if not _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please wait before retrying.",
                "retry_after": _RATE_LIMIT_WINDOW_S,
            },
        )

    try:
        response_text = await query_mechanic_agent(
            query=query.query,
            car_context=query.vehicle_context,
            history=[m.model_dump() for m in query.history],
        )
        return DiagnosticResponse(response=response_text)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Diagnostic engine failure: {str(e)}"
        ) from e


@router.post("/diagnostics/vin-rag-brief", response_model=VINRagResponse)
async def vin_rag_brief(request: VINRagRequest) -> VINRagResponse:
    """
    Fire an internal RAG query for additional vehicle-specific technical depth.
    Called async by frontend after displaying the instant technical brief.
    Returns corpus-sourced data as a follow-up chat bubble.
    """
    query = (
        f"Provide technical details for {request.vehicle_context}: "
        f"wiring, faults, sensor testing, and TSB notes."
    )
    try:
        result = await query_mechanic_agent(
            query=query,
            car_context=request.vehicle_context,
        )
        return VINRagResponse(content=result)
    except Exception as e:
        _log.error("VIN RAG brief failed: %s", e)
        return VINRagResponse(
            content=(
                "_No additional data retrieved from knowledge base for this vehicle._"
            )
        )


@router.post("/diagnostics/vin-decode", response_model=VINDecodeResponse)
async def decode_vin(request: VINDecodeRequest) -> VINDecodeResponse:
    """
    Decode a 17-character VIN using a ranked 3-tier cascade:
      Tier 1 - Local WMI table  (instant, Egyptian/MENA priority)
      Tier 2 - auto.dev API     (global, returns engine/transmission/trim)
      Tier 3 - NHTSA            (North American WMIs only)
    Returns vehicle_context_suggestion for pre-populating the RAG engine.
    """
    vin = request.vin.upper().strip()

    if not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
        return VINDecodeResponse(
            vin=vin,
            valid=False,
            message="VIN contains invalid characters. I, O, Q not allowed.",
            confidence="low",
        )

    # Cache lookup — valid VIN specs never change
    if cached := _vin_cache_get(vin):
        _log.info("VIN cache hit: %s…", vin[:8])
        return cached

    check_valid = _validate_vin_check_digit(vin)
    wmi = vin[:3]
    model_year = _MODEL_YEAR_MAP.get(vin[9], "Unknown")
    wmi_data = _WMI_TABLE.get(wmi)

    # -- Tier 1: Local WMI table ----------------------------------------------
    if wmi_data:
        make = wmi_data["make"]
        country = wmi_data["country"]
        context = _build_vehicle_context_suggestion(make, model_year, "")
        # Tier 1 has no model data — passing the raw VIN string
        # as a model hint was semantically wrong.
        cd_msg = (
            "Check digit valid."
            if check_valid
            else ("Check digit mismatch -- VIN may be incorrectly entered.")
        )

        decode_data = {
            "confidence": "high",
            "model_year": model_year,
            "country": country,
            "wmi": wmi,
            "message": f"VIN decoded successfully. {cd_msg}",
        }

        resp = VINDecodeResponse(
            vin=vin,
            valid=True,
            make=make,
            model_year=model_year,
            wmi=wmi,
            country=country,
            vehicle_context_suggestion=context,
            confidence="high",
            message=decode_data["message"],
        )

        # Apply Layer 2 Brief
        spec = get_spec(context)
        if spec:
            resp.technical_brief = format_vehicle_brief(vin, spec, decode_data)
            resp.has_rag_followup = True

        result = apply_enrichment(
            resp,
            make=make,
            model="",  # Tier 1 WMI is general/model-agnostic
            year=model_year,
        )
        # Ensure RAG follow-up fires even when no priority spec
        # was found. apply_enrichment may have populated
        # engine_code and known_issues from _POWERTRAIN_PROFILES.
        if not result.has_rag_followup:
            result.has_rag_followup = True
        _vin_cache_set(vin, result)
        return result

    # -- Tier 2: auto.dev Global VIN API --------------------------------------
    if settings.AUTO_DEV_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    f"https://api.auto.dev/vin/{vin}",
                    headers={
                        "Authorization": f"Bearer {settings.AUTO_DEV_API_KEY}",
                        "Content-Type": "application/json",
                    },
                )
            if resp.status_code == 200:
                data = resp.json()
                veh: dict[str, object] = data.get("vehicle") or {}  # type: ignore[assignment]
                make_raw = str(data.get("make") or veh.get("make") or "")
                model_raw = str(data.get("model") or "")
                year_raw = str(veh.get("year") or model_year)
                engine_raw = str(data.get("engine") or "")
                transmission_raw = str(data.get("transmission") or "")
                trim_raw = str(data.get("trim") or "")
                country_raw = str(data.get("origin") or "")
                checksum_ok = bool(data.get("checksum", check_valid))

                if make_raw:
                    make_display = " ".join(
                        filter(None, [make_raw.title(), model_raw, trim_raw])
                    )
                    context = _build_vehicle_context_suggestion(
                        make_raw,
                        year_raw,
                        model_raw,  # model_raw from auto.dev
                    )
                    if engine_raw or transmission_raw:
                        spec_hint = " / ".join(
                            filter(None, [engine_raw, transmission_raw])
                        )
                        if spec_hint.lower() not in context.lower():
                            context = f"{context} [{spec_hint}]"
                    cd_msg = (
                        "Check digit valid."
                        if checksum_ok
                        else ("Check digit mismatch -- verify VIN.")
                    )

                    decode_data = {
                        "confidence": "high",
                        "model_year": year_raw,
                        "country": country_raw,
                        "wmi": wmi,
                        "message": f"Decoded via auto.dev global DB. {cd_msg}",
                    }

                    resp = VINDecodeResponse(
                        vin=vin,
                        valid=True,
                        make=make_display or make_raw,
                        model_year=year_raw,
                        wmi=wmi,
                        country=country_raw,
                        vehicle_context_suggestion=context,
                        confidence="high",
                        message=decode_data["message"],
                    )

                    # Apply Layer 2 Brief
                    spec = get_spec(context)
                    if spec:
                        resp.technical_brief = format_vehicle_brief(
                            vin, spec, decode_data
                        )
                        resp.has_rag_followup = True

                    result = apply_enrichment(
                        resp,
                        make=make_raw,
                        model=model_raw,
                        year=year_raw,
                    )
                    if not result.has_rag_followup:
                        result.has_rag_followup = True
                    _vin_cache_set(vin, result)
                    return result
        except Exception as exc:
            _log.warning("auto.dev VIN decode failed for %s: %s", vin, exc)

    # -- Tier 3: NHTSA — North American WMIs only -----------------------------
    if vin[0] in ("1", "2", "3", "4", "5"):
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(
                    "https://vpic.nhtsa.dot.gov/api/vehicles/"
                    f"decodevin/{vin}?format=json"
                )
                resp.raise_for_status()
                _skip = {"null", "Not Applicable", ""}
                results = {
                    item["Variable"]: item["Value"]
                    for item in resp.json().get("Results", [])
                    if item.get("Value") and item["Value"] not in _skip
                }
                make = results.get("Make", "")
                model = results.get("Model", "")
                year = results.get("Model Year", model_year)
                country = results.get("Plant Country", "")
                if make:
                    context = _build_vehicle_context_suggestion(
                        make,
                        year,
                        model,  # model from NHTSA results
                    )
                    cd_msg = (
                        "Check digit valid."
                        if check_valid
                        else ("Check digit mismatch -- verify VIN.")
                    )

                    decode_data = {
                        "confidence": "medium",
                        "model_year": year,
                        "country": country,
                        "wmi": wmi,
                        "message": f"Decoded via NHTSA database. {cd_msg}",
                    }

                    resp = VINDecodeResponse(
                        vin=vin,
                        valid=True,
                        make=f"{make} {model}".strip(),
                        model_year=year,
                        wmi=wmi,
                        country=country,
                        vehicle_context_suggestion=context,
                        confidence="medium",
                        message=decode_data["message"],
                    )

                    # Apply Layer 2 Brief
                    spec = get_spec(context)
                    if spec:
                        resp.technical_brief = format_vehicle_brief(
                            vin, spec, decode_data
                        )
                        resp.has_rag_followup = True

                    result = apply_enrichment(
                        resp,
                        make=make,
                        model=model,
                        year=year,
                    )
                    if not result.has_rag_followup:
                        result.has_rag_followup = True
                    _vin_cache_set(vin, result)
                    return result
        except Exception as exc:
            _log.warning("NHTSA VIN decode failed for %s: %s", vin, exc)

    # -- Final fallback -------------------------------------------------------
    return VINDecodeResponse(
        vin=vin,
        valid=check_valid,
        wmi=wmi,
        model_year=model_year,
        confidence="low",
        has_rag_followup=True,
        message=(
            "VIN is valid but manufacturer unidentified. "
            "If this is an Egypt-assembled vehicle (Nissan NASCO, "
            "Kia, or other local assembly), WMI codes for these "
            "plants are not yet confirmed in our database. "
            "Please set vehicle context manually."
        ),
    )


# ---------------------------------------------------------------------------
# Ingestion Endpoints
# ---------------------------------------------------------------------------


async def _save_upload(file: UploadFile, dest_path: Path) -> None:
    """Write upload file to disk without blocking the event loop."""
    loop = asyncio.get_event_loop()
    try:
        content = await file.read()
        await loop.run_in_executor(None, dest_path.write_bytes, content)
    finally:
        await file.seek(0)


@router.post("/ingestion/upload", response_model=IngestionResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    vehicle_context: str = Form(...),
    file: Annotated[UploadFile, File()] = ...,
) -> IngestionResponse:
    """Upload OEM PDF manuals for vectorization and indexing."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    upload_path = Path(settings.UPLOAD_DIR) / file.filename

    try:
        await _save_upload(file, upload_path)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"File upload failed: {str(e)}"
        ) from e

    background_tasks.add_task(ingest_manual, str(upload_path))

    return IngestionResponse(
        status="pending",
        message=(
            f"Ingestion started for {file.filename} with context: {vehicle_context}"
        ),
        filename=file.filename,
    )


@router.post("/ingestion/web", response_model=IngestionResponse)
async def upload_from_web(
    background_tasks: BackgroundTasks,
    request: WebIngestionRequest,
) -> IngestionResponse:
    """Ingest manuals from a URL (manuals.co or direct PDF)."""
    background_tasks.add_task(
        web_ingester.process_url, request.url, request.vehicle_context
    )
    return IngestionResponse(
        status="pending",
        message=f"Web ingestion started for {request.url}",
    )
