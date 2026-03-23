"""
RAG engine for Pojehat performing vehicle diagnostics.

2026 architecture: HyDE query expansion, multi-collection RRF retrieval,
score-threshold gating, singleton lifecycle, and structured fallback.
"""

import hashlib
import logging
from collections import defaultdict
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from llama_index.core import (
    StorageContext,
    VectorStoreIndex,
    get_response_synthesizer,
)
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.prompts import ChatPromptTemplate
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openrouter import OpenRouter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import FieldCondition, Filter, MatchText, MatchValue

from src.core.config import HV_SRS_KEYWORDS, PROTOCOL_KEYWORDS, settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants — safety gate + conditional prompt injection blocks
# ---------------------------------------------------------------------------

_HV_SRS_SAFETY_PREFIX = (
    "### ⚠️ تحذير السلامة — إلزامي\n\n"
    "> **HV Systems:** افصل الـ service plug وانتظر 10 دقائق قبل أي تدخل.\n"
    "> **SRS/Airbags:** افصل البطارية وانتظر 60 ثانية"
    " — لا تقترب من الـ squib wires.\n"
    "> **لا تعمل على أنظمة HV/SRS إلا بتدريب متخصص ومعدات عزل معتمدة.**\n"
    "\n---\n"
)

_DTC_DECODE_BLOCK = (
    "---\n\n"
    "### DTC Prefix Decode Protocol (use when code not in corpus)\n\n"
    "If a DTC code is not found in retrieved documents, decode it "
    "structurally instead of saying 'unknown':\n\n"
    "**Char 1 — System:** P=Powertrain | B=Body | C=Chassis | U=Network\n\n"
    "**Char 2 — Type:** 0=SAE/Generic | 1,2,3=Manufacturer-specific\n\n"
    "**Chars 3–4 — Subsystem:**\n"
    "01=Fuel/Air | 02=Injector circuit | 03=Ignition/Misfire\n"
    "04=Aux emission | 05=Speed/Idle | 06=Computer | 07–08=Transmission\n\n"
    "**Format for unknown DTC:**\n"
    "1. Decode structure using the protocol above\n"
    "2. State: 'هذا الكود غير موجود في قاعدة البيانات — "
    "التحليل التالي مبني على بنية الكود (استنتاج هندسي)'\n"
    "3. Give probable subsystem, common causes, generic diagnostic start\n"
    "4. Recommend checking manufacturer TSB for vehicle-specific meaning\n"
)

_SENSOR_GROUNDING_BLOCK = (
    "---\n\n"
    "### Sensor Value Grounding Rules (STRICT)\n\n"
    "When citing sensor values (voltages, resistances, frequencies):\n\n"
    "- **Only cite retrieved values** — tag: (من قاعدة البيانات — [source])\n"
    "- **If not in context** — provide industry range, tag: "
    "(نطاق صناعي — استنتاج هندسي)\n"
    "- **Never present memorized values as vehicle-specific** without the tag\n"
    "- **Resistance values**: state condition (cold/hot, connector state)\n"
    "- **Voltage values**: state ignition state (KOEO / KOER)\n\n"
    "✅ 'مقاومة حساس الأكسجين: 5–20 أوم (نطاق صناعي — استنتاج هندسي)'\n"
    "❌ 'مقاومة الحساس: 950 أوم' — forbidden, no source\n"
)

# Protocol keywords triggering the structured protocol response template.
_PROTOCOL_HINT_KWS: tuple[str, ...] = (
    "can bus", "uds ", "doip", "lin bus", "obd-ii protocol",
    "diagnostic session", "consult", "techstream", "launch x431",
)


class _IntentType(StrEnum):
    FAULT_DIAGNOSIS   = "FAULT_DIAGNOSIS"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    CATALOG_LOOKUP    = "CATALOG_LOOKUP"
    KNOWLEDGE_AUDIT   = "KNOWLEDGE_AUDIT"
    SYSTEM_QUERY      = "SYSTEM_QUERY"
    HV_SRS_QUERY      = "HV_SRS_QUERY"


async def _classify_intent(query: str) -> _IntentType:
    """
    Classify query intent before retrieval (~80 token call).
    Falls back to FAULT_DIAGNOSIS on any failure.
    """
    prompt = (
        "Classify the following query into exactly one category. "
        "Reply with ONLY the category name — no explanation, "
        "no punctuation, nothing else.\n\n"
        "FAULT_DIAGNOSIS\n"
        "  A vehicle symptom, DTC code, sensor failure, wiring fault, "
        "or request for a diagnostic procedure on a specific problem.\n"
        "  Examples: 'C1241 wheel speed sensor', "
        "'P0300 misfire Corolla', 'rough idle on cold start'\n\n"
        "GENERAL_KNOWLEDGE\n"
        "  How an automotive system works, theory, principles, general "
        "specs not tied to a specific fault, and ANY query about diagnostic "
        "protocols (CAN bus, UDS, DoIP, LIN, OBD-II internals, diagnostic "
        "session management, manufacturer-specific tool procedures).\n"
        "  Examples: 'how does a CVT work', 'explain CAN bus', "
        "'what is variable valve timing', 'how does UDS work', "
        "'CONSULT III procedure Nissan', 'DoIP connection setup'\n\n"
        f"Query: {query}\n\n"
        "Category:"
    )
    try:
        response = await _get_hyde_llm().acomplete(prompt)
        raw = str(response).strip().upper().split()[0]
        try:
            return cast(_IntentType, _IntentType(raw))
        except ValueError:
            return _IntentType.FAULT_DIAGNOSIS
    except (ValueError, RuntimeError, OSError) as e:
        logger.warning(
            "Intent classification failed (%s) — defaulting to FAULT_DIAGNOSIS.", e
        )
        return _IntentType.FAULT_DIAGNOSIS

# ---------------------------------------------------------------------------
# Collection routing table — confirmed from live Qdrant schema inspection
# ---------------------------------------------------------------------------
# pojehat_hybrid_v1  → ingested with default unnamed vector → vector_name=None
# pojehat_obd_ecu_v1 → ingested with named text-dense + text-sparse → hybrid
_COLLECTION_CFG: list[dict] = [
    {
        "name": "pojehat_hybrid_v1",
        "vector_name": None,
        "sparse_vector_name": "text-sparse-new",
        "enable_hybrid": True,
    },
    {
        "name": "pojehat_obd_ecu_v1",
        "vector_name": "text-dense",
        "sparse_vector_name": "text-sparse",
        "enable_hybrid": True,
    },
]

# ---------------------------------------------------------------------------
# Singletons — one instance per process lifetime, reused on every request
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_llm() -> OpenRouter:
    """Cached LLM singleton — tuned for deterministic Tier-3 diagnostics."""
    return OpenRouter(
        model=settings.LLM_MODEL_NAME,
        api_key=settings.GROK_API_KEY,
        temperature=0.2,       # Diagnostic facts, not creativity
        max_tokens=4096,       # Detailed step-by-step diagnostic breakdown
        context_window=128000,
        additional_kwargs={"top_p": 0.9},
    )


@lru_cache(maxsize=1)
def _get_hyde_llm() -> OpenRouter:
    """Lightweight LLM for HyDE expansion — fast, cheap, 3-sentence output only."""
    return OpenRouter(
        model=settings.HYDE_MODEL_NAME,
        api_key=settings.GROK_API_KEY,
        temperature=0.1,   # Even more deterministic for OEM-style text generation
        max_tokens=300,    # HyDE only needs 3 technical sentences
        context_window=4000,
        additional_kwargs={"top_p": 0.85},
    )


@lru_cache(maxsize=1)
def _get_audit_llm() -> OpenRouter:
    """
    Deterministic LLM for KNOWLEDGE_AUDIT and structured output.
    temperature=0.0 ensures identical inputs produce identical confidence scores.
    top_p=1.0 disables nucleus sampling — full greedy decoding.
    """
    return OpenRouter(
        model=settings.LLM_MODEL_NAME,
        api_key=settings.GROK_API_KEY,
        temperature=0.0,
        max_tokens=4096,
        context_window=128000,
        additional_kwargs={"top_p": 1.0},
    )


from typing import List
import httpx
from llama_index.core.embeddings import BaseEmbedding

class CustomOpenRouterEmbedding(BaseEmbedding):
    """Bypasses LlamaIndex Pydantic enums to safely hit OpenRouter."""
    
    def _get_query_embedding(self, query: str) -> List[float]:
        # Sync fallback (mostly unused in async paths)
        with httpx.Client() as client:
            resp = client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                json={"model": settings.EMBED_MODEL, "input": query},
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    async def _aget_query_embedding(self, query: str) -> List[float]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/embeddings",
                headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                json={"model": settings.EMBED_MODEL, "input": query},
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()["data"][0]["embedding"]

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._get_query_embedding(text)

    async def _aget_text_embedding(self, text: str) -> List[float]:
        return await self._aget_query_embedding(text)

@lru_cache(maxsize=1)
def _get_embed_model() -> BaseEmbedding:
    return CustomOpenRouterEmbedding()


def _parse_vehicle_filter(car_context: str) -> Filter | None:
    """
    Build a soft Qdrant payload filter from the vehicle context string.

    Strategy:
    - Extract meaningful tokens (length >= 2) from car_context
    - Build OR conditions across both vehicle_context and file_name fields
    - Short brand names (MG, KIA) are now handled correctly
    - Returns None only if car_context is empty or contains no usable tokens
    """
    if not car_context or not car_context.strip():
        return None

    # Extract tokens: keep alpha-numeric tokens of length >= 2
    # This correctly handles: "MG ZS", "KIA Sportage", "Nissan Sunny B17"
    raw_tokens = car_context.strip().split()
    tokens = [t for t in raw_tokens if len(t) >= 2]

    if not tokens:
        return None

    # Use the most specific token available:
    # Prefer longer tokens (model names) over short brand codes
    # "Nissan Sunny B17" → primary="Sunny", fallback="Nissan"
    # "MG ZS" → primary="MG", fallback="ZS"
    primary_token = max(tokens, key=len)

    should_conditions = [
        FieldCondition(
            key="vehicle_context",
            match=MatchText(text=primary_token),
        ),
        FieldCondition(
            key="file_name",
            match=MatchText(text=primary_token),
        ),
    ]

    # Add brand token as additional signal if different from primary
    brand_token = tokens[0]
    if brand_token != primary_token and len(brand_token) >= 2:
        should_conditions.extend([
            FieldCondition(
                key="vehicle_context",
                match=MatchText(text=brand_token),
            ),
            FieldCondition(
                key="file_name",
                match=MatchText(text=brand_token),
            ),
        ])

    return Filter(should=should_conditions)


def _build_domain_filter(domain_tags: list[str]) -> Filter:
    """
    Payload filter on domain_tag field (indexed via B2).
    Restricts retrieval to pre-tagged domain values within the existing
    collection — no new collections are created.
    """
    return Filter(
        should=[
            FieldCondition(
                key="domain_tag",
                match=MatchValue(value=tag),
            )
            for tag in domain_tags
        ]
    )

@lru_cache(maxsize=1)
def _get_qdrant_client() -> AsyncQdrantClient:
    """Cached async Qdrant client singleton."""
    return AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rrf_merge(
    ranked_lists: list[list[NodeWithScore]],
    k: int = 60,
) -> list[NodeWithScore]:
    """
    Reciprocal Rank Fusion across multiple ranked node lists.

    Deduplicates nodes by content hash. Returns a fused, re-ranked list where
    each node's score reflects its combined rank across all source collections.
    O(n) — no external model dependency.
    """
    rrf_scores: dict[str, float] = {}
    nodes_by_key: dict[str, NodeWithScore] = {}

    for ranked in ranked_lists:
        for rank, node in enumerate(ranked, start=1):
            node_key = hashlib.sha256(
                node.get_content().encode()
            ).hexdigest()[:16]
            rrf_scores[node_key] = rrf_scores.get(node_key, 0.0) + 1.0 / (k + rank)
            nodes_by_key[node_key] = node

    fused_order = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    result: list[NodeWithScore] = []
    for node_key, rrf_score in fused_order:
        node = nodes_by_key[node_key]
        node.score = rrf_score  # surface RRF score for transparency in logs
        result.append(node)

    return result


def _compute_retrieval_metrics(nodes: list[NodeWithScore]) -> dict:
    from typing import TypedDict
    class SourceStats(TypedDict):
        count: int
        scores: list[float]

    domain_stats: defaultdict[str, SourceStats] = defaultdict(
        lambda: cast(SourceStats, {"count": 0, "scores": []})
    )
    for node in nodes:
        source = (
            node.node.metadata.get("file_name")
            or node.node.metadata.get("source")
            or "unknown"
        )
        domain_stats[source]["count"] += 1
        domain_stats[source]["scores"].append(float(node.score or 0.0))
    result = {}
    for source, data in domain_stats.items():
        scores = cast(list[float], data["scores"])
        # RRF scores usually fall between 0.01 and 0.04
        max_s = float(max(scores))
        # Audit/Diagnostic scaling: lower floor (0.009) ensures broad audits show coverage
        floor, ceil = 0.009, 0.035
        pct = (max_s - floor) / (ceil - floor) * 100.0
        result[source] = {
            "chunk_count": int(data["count"]),
            "avg_rrf_score": round(float(sum(scores)) / float(len(scores)), 5),
            "top_rrf_score": round(max_s, 5),
            "coverage_pct": round(min(100.0, max(0.0, pct)), 1),
        }
    return result


async def _hyde_expand(query: str, car_context: str) -> str:
    """
    Hypothetical Document Embeddings (HyDE) query expansion.

    Uses a lightweight, low-temperature LLM call to generate a 3-sentence
    OEM-style technical answer. Embedding this hypothetical document vector
    bridges the vocabulary gap between colloquial queries and technical docs.
    Uses a dedicated fast LLM singleton to avoid blocking the main synthesis.
    """
    hyde_prompt = (
        "You are an automotive expert. Write a concise 3-sentence technical "
        "answer to this diagnostic question as it would appear in an OEM service "
        "manual. Be specific about part names, codes, and failure modes.\n\n"
        f"Vehicle: {car_context}\n"
        f"Question: {query}"
    )
    try:
        hyde_llm = _get_hyde_llm()
        response = await hyde_llm.acomplete(hyde_prompt)
        expanded = str(response).strip()
        logger.info("HyDE expansion: %d chars generated.", len(expanded))
        return expanded
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("HyDE expansion failed — using raw query. Reason: %s", e)
        return query


def _build_structure_block(intent: _IntentType, query: str = "") -> str:
    """
    Return the mandatory output structure for this intent type.
    Replaces the broken conditional prose in the static system prompt
    that Grok and Command R both ignore in favour of pattern-matching.
    """
    if intent == _IntentType.FAULT_DIAGNOSIS:
        return (
            "### Recommended structure for FAULT_DIAGNOSIS\n\n"
            "For diagnostic queries (DTCs, symptoms, failures):\n"
            "1. **◆ Root Cause Analysis** — most probable cause first\n"
            "2. **○ Circuit/Component Specs** — voltages, resistances, exact values\n"
            "3. **▸ Test Procedure** — numbered steps with expected readings\n"
            "4. **▸ Fix Procedure** — ordered repair steps\n"
            "Adapt sections as needed — simple symptoms may combine.\n\n"
            "### Gap Disclosure Rules\n\n"
            "If corpus data is missing for the queried vehicle or component:\n"
            "- Unknown vehicle: state 'لا توجد بيانات OEM خاصة بهذا الموديل' — "
            "then continue with engineering-knowledge response\n"
            "- All inferred values (not from retrieved docs): "
            "tag with (استنتاج هندسي)\n"
            "- All corpus-sourced values: tag with (من قاعدة البيانات)\n"
            "- Unknown DTC codes: apply DTC Prefix Decode Protocol below\n"
            "- Never present a generic value as vehicle-specific "
            "without the source tag\n"
        )
    if intent == _IntentType.GENERAL_KNOWLEDGE:
        if any(kw in query.lower() for kw in PROTOCOL_KEYWORDS):
            return (
                "### Recommended Structure (Protocol Query)\n\n"
                "1. **🔵 Protocol Overview** — architecture, layers, frame format\n"
                "2. **🔵 Automotive Application** — how it's used "
                "in the queried context\n"
                "3. **🟢 Practical Diagnostic Use** — what a technician can do with "
                "a Launch X431 or generic OBD-II scanner\n"
                "4. **🔵 Egyptian Market Note** — which priority vehicles "
                "1. **○ Protocol Overview** — architecture, layers, frame format\n"
                "2. **○ Automotive Application** — how it's used "
                "in the queried context\n"
                "3. **▸ Practical Diagnostic Use** — what a technician can do with "
                "a Launch X431 or generic OBD-II scanner\n"
                "4. **○ Egyptian Market Note** — which priority vehicles "
                "use this protocol\n"
            )
        return (
            "### Recommended structure for GENERAL_KNOWLEDGE\n\n"
            "For theory/explanation queries, consider this flow:\n"
            "1. **○ Theory/Principle** — explain how it works\n"
            "2. **▸ Real-World Example** — Egyptian market vehicle application\n"
            "3. **▸ Common Issues** — typical failure modes if relevant\n"
            "Structure flexibly based on what the user asked.\n"
        )
    if intent == _IntentType.CATALOG_LOOKUP:
        return (
            "### Recommended structure for CATALOG_LOOKUP\n\n"
            "Present specifications/data with **○ Specifications** heading. "
            "Use tables for organized data. Add context/notes "
            "if helpful but keep it focused.\n"
        )
    if intent == _IntentType.KNOWLEDGE_AUDIT:
        return (
            "### Mandatory structure for KNOWLEDGE_AUDIT\n\n"
            "You are auditing ONLY the documents retrieved in this session. "
            "You cannot see the full Qdrant corpus — only what was returned "
            "in this retrieval pass. Follow these rules strictly:\n\n"
            "1. **Ground every claim in retrieved context only.** "
            "Do NOT invent categories or coverage claims for data you did "
            "not receive. If a domain is absent from retrieved nodes, "
            "state: 'No documents retrieved for this domain in this pass.'\n\n"
            "2. **Structure your response as follows:**\n"
            "   - **○ Retrieved Document Summary** — list each distinct source found\n"
            "   - **○ Coverage Table** — Markdown table with columns: "
            "Domain | Topics Covered | Confidence | Notes. "
            "For Confidence, render a visual block bar: use █ (filled) and ░ (empty) "
            "to represent coverage. 10 blocks total. Examples: "
            "████████░░ 80%, ██████████ 100%, ████░░░░░░ 40%. "
            "Always follow the bar with the numeric percentage. "
            "Never use plain text percentages alone.\n"
            "   - **⚠ Gaps and Limitations** — explicitly list domains with Low "
            "or vehicle types for which NO documents were retrieved.\n"
            "   - **Retrieval Caveat** — end with this exact sentence: "
            "'This analysis reflects the documents retrieved in this "
            "session only and does not represent the complete corpus.'\n\n"
            "3. **Do NOT open with Root Cause Analysis.** "
            "There is no fault to diagnose here.\n"
        )
    if intent == _IntentType.HV_SRS_QUERY:
        return (
            "### Mandatory Structure for HV_SRS_QUERY\n\n"
            "This query involves high-voltage or SRS systems. "
            "Apply these rules before writing ANY diagnostic content:\n\n"
            "**Rule 1 — Structure required:**\n"
            "1. **○ System Overview** — how the system works\n"
            "2. **◆ Fault Analysis** — DTC meaning and probable root cause\n"
            "3. **▸ Safe Diagnostic Procedure** — only steps that do NOT require "
            "specialized dealer tools\n"
            "4. **⚠ When to Stop** — explicit list of actions requiring a "
            "requiring a specialist\n\n"
            "**Rule 2 — Gap disclosure:** If corpus has no data for this "
            "vehicle's HV/SRS system, state: 'لا توجد بيانات OEM لهذه السيارة — "
            "المعلومات التالية مبنية على مبادئ هندسية عامة (استنتاج هندسي)'. "
            "Then provide general principles. "
            "Never present inferred data as OEM specs.\n"
        )
    if intent == _IntentType.GENERAL_KNOWLEDGE:
        # Check if it's a protocol-focused general knowledge query
        is_protocol_topic = any(
            kw in query.lower() for kw in _PROTOCOL_HINT_KWS
        )
        if is_protocol_topic:
            return (
                "### Recommended Structure (Protocol Query)\n\n"
                "1. **○ Protocol Overview** — architecture, layers, frame format\n"
                "2. **○ Automotive Application** — how it's used in modern vehicles\n"
                "3. **▸ Practical Diagnostic Use** — what a technician can do with this\n"
                "4. **○ Egyptian Market Note** — which priority vehicles use this "
                "protocol and where\n"
            )
    return ""


def _build_qa_template(system_prompt: str) -> ChatPromptTemplate:
    """
    Constructs a LlamaIndex ChatPromptTemplate that places the system
    instructions in the system role and the retrieved context + user query
    in the user role, matching the expected format for high-intelligence LLMs.
    """
    return ChatPromptTemplate(
        message_templates=[
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=system_prompt,
            ),
            ChatMessage(
                role=MessageRole.USER,
                content=(
                    "Context:\n"
                    "---------------------\n"
                    "{context_str}\n"
                    "---------------------\n\n"
                    "Query: {query_str}"
                ),
            ),
        ]
    )


# ---------------------------------------------------------------------------
def _generate_grounding_bar_html(confidence_pct: int) -> str:
    """Centralized HTML generator for Pojehat grounding bars."""
    if confidence_pct >= 80:
        color = "#639922" # ok
    elif confidence_pct >= 50:
        color = "#ef9f27" # warn
    else:
        color = "#e24b4a" # crit

    # V2: Higher contrast, larger text, better spacing
    return (
        "<div style=\"display:flex;flex-direction:column;align-items:flex-start;gap:4px;"
        "margin-bottom:8px\">\n"
        "<span class=\"poj-bar-track\" style=\"margin-left:0;width:120px;height:8px;"
        "background-color:#eee;border-radius:4px;overflow:hidden\">\n"
        f"<span class=\"poj-bar-fill\" style=\"display:block;height:100%;"
        f"width:{confidence_pct}%;background-color:{color};transition:width 0.3s ease\">"
        "</span>\n"
        "</span>\n"
        f"<span style=\"font-size:0.95em;font-weight:800;color:{color};line-height:1.2\">"
        f"{confidence_pct}%</span>\n"
        "</div>"
    )


async def query_mechanic_agent(
    query: str,
    car_context: str,
    history: list[Any] | None = None,
) -> str:
    """
    Tier-3 Master Technician AI that responds in technical Egyptian Arabic slang.

    Pipeline:
      1. Intent classification (prevents meta-query hallucination)
      2. SYSTEM_QUERY short-circuit (no retrieval for meta-queries)
      3. HyDE query expansion (vocabulary bridging)
      4. Vehicle-aware retrieval with soft payload filter
      5. Multi-collection parallel retrieval with correct per-schema vector names
      6. Reciprocal Rank Fusion deduplication & re-ranking
      7. Score threshold gating (≥ RAG_SCORE_THRESHOLD) with structured fallback
      8. LLM response synthesis
    """
    llm = _get_llm()
    embed_model = _get_embed_model()
    client = _get_qdrant_client()

    # 1. Keyword pre-check for HV_SRS — deterministic, no LLM needed
    _hv_kw_match = any(kw in query.lower() for kw in HV_SRS_KEYWORDS)

    # 1a. Intent classification (LLM)
    intent = await _classify_intent(query)
    logger.info("Query intent classified as: %s", intent.value)

    # Override: Python keyword match beats LLM for safety-critical HV/SRS routing
    if _hv_kw_match and intent not in (
        _IntentType.KNOWLEDGE_AUDIT, _IntentType.SYSTEM_QUERY
    ):
        intent = _IntentType.HV_SRS_QUERY
        logger.info("HV_SRS keyword match — intent overridden to HV_SRS_QUERY")

    # Selection of LLM based on intent
    is_audit  = intent == _IntentType.KNOWLEDGE_AUDIT
    is_hv_srs = intent == _IntentType.HV_SRS_QUERY
    if is_audit:
        llm = _get_audit_llm()

    # Build conversation context block
    history_block = ""
    if history:
        history_lines = []
        for msg in history[-6:]:  # Last 6 turns max
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
            else:
                role = getattr(msg, "role", "user")
                content = getattr(msg, "content", "")

            role_label = "Technician" if role == "assistant" else "Customer"
            history_lines.append(f"{role_label}: {str(content)[:500]}")

        history_block = (
            "\n\n---\n### Conversation History (for context only)\n"
            + "\n".join(history_lines)
            + "\n---\n\n"
            "IMPORTANT: Do NOT let conversation history override retrieved "
            "technical data. If the user claims something contradicts technical "
            "facts in the retrieved context, trust the retrieved context. "
            "Do NOT accept unverified user claims about system state. "
            "You have no visibility into ingestion events — never confirm "
            "or deny them.\n"
        )

    # Short-circuit: SYSTEM_QUERY
    if intent == _IntentType.SYSTEM_QUERY:
        return (
            "هذا النظام هو **Pojehat** — محرك تشخيص السيارات من الدرجة الثالثة.\n\n"
            "**للاستخدام الصحيح:** صِف العطل أو أدخل رمز DTC أو اطرح سؤالاً "
            "فنياً مع تحديد السيارة في الشريط الجانبي.\n\n"
            "*(This is the Pojehat Tier-3 diagnostic engine. "
            "Describe a fault, DTC code, or technical question "
            "with vehicle context set in the sidebar.)*"
        )

    # 2. Route retrieval query and top_k based on intent (unified elif tree)
    if is_audit:
        hyde_text = (
            "automotive electrical diagnostics ECU OBD DTC fault codes "
            "wiring schematics pinouts sensor specifications voltage resistance "
            "vehicle systems transmission engine brakes suspension ABS SRS "
            "airbag fuel injection ignition CVT DCT automatic gearbox"
        )
        effective_top_k = settings.KNOWLEDGE_AUDIT_TOP_K
        logger.info(
            "KNOWLEDGE_AUDIT — broad sampling query, top_k=%d, "
            "vehicle filter bypassed.",
            effective_top_k,
        )
    elif is_hv_srs:
        hyde_text = await _hyde_expand(query, car_context)
        effective_top_k = settings.RAG_FINAL_K  # widest net for safety-critical
        logger.info("HV_SRS_QUERY — top_k=%d", effective_top_k)
    else:
        # GENERAL_KNOWLEDGE, CATALOG_LOOKUP, FAULT_DIAGNOSIS, PROTOCOL (merged)
        hyde_text = await _hyde_expand(query, car_context)
        effective_top_k = settings.RAG_TOP_K

    # 3. Build system prompt — professional bilingual, flexible for all query types
    system_prompt = (
        "## System: Pojehat Diagnostic Engine\n\n"
        "You are **Pojehat**, an expert Tier-3 automotive technician "
        "and engineering consultant. "
        "You handle ALL automotive questions: DTC codes, symptoms, "
        "component theory, "
        "repair procedures, specifications, troubleshooting, and "
        "general technical queries.\n\n"
        "**Communication Style:**\n"
        "- **Bilingual**: technical terms in English, explanations in Modern "
        "Standard Arabic with Egyptian colloquial clarity\n"
        "- **Professional but approachable** — like a master technician teaching "
        "an apprentice\n"
        "- **Adapt your response structure to the question type** (don't force "
        "fault diagnosis format on theory questions)\n\n"
        f"**Vehicle Context:** {car_context}\n\n"
        "---\n\n"
        "### Response Quality Standards\n\n"
        "- **Be comprehensive**: Include specific values "
        "(voltages, resistances, torque specs) when available\n"
        "- **Be practical**: Focus on real-world diagnostics "
        "with actual Egyptian market vehicles\n"
        "- **Be honest**: If inferring from engineering principles "
        "(not retrieved docs), note: \"(استنتاج هندسي)\"\n"
        "- **Be flexible**: Structure your answer to fit the question "
        "\u2014 not every query needs Root Cause Analysis\n"
        f"{_build_structure_block(intent, query)}\n"
        "---\n\n"
        "### Formatting Rules\n"
    "1. Grounding Confidence Bar: The HTML `div` provided must be the ABSOLUTE FIRST line of your response.\n"
        "   ◆ fault / critical finding\n"
        "   ▸ procedure step or recommendation\n"
        "   ○ specification or data value\n"
        "   ⚠ safety warning — mandatory, never remove\n"
        "   ✓ verified / confirmed finding\n"
        "   ✗ ruled-out cause\n"
        "   ⚙ mechanical system\n"
        "   ⚡ electrical / electronic system\n"
        "   NEVER use: 🚗 🔧 📊 📟 🌍 🔍 🤖 🔴 🟡 🟢 🔵 as heading markers.\n"
        "   These break professional tone. Use the minimal markers above.\n"
        "2. **Bold** component names, codes, and spec values on first mention.\n"
        "3. Tables for specs/pinouts/DTC lists. "
        "Fenced ``` blocks for ECU/DTC data.\n"
        "4. Bullets: ▸ primary cause, • secondary, ◦ tertiary. "
        "Numbered steps for procedures.\n"
        "5. RTL/LTR discipline: Arabic explanation text must be on its own line. "
        "Never mix Arabic sentence structure with English sentence structure "
        "on the same line. English technical terms (DTC codes, component names, "
        "resistance values) are always written in English even within Arabic "
        "paragraphs — this is correct. But never open a line in English then "
        "switch mid-sentence to Arabic prose.\n"
        "6. Grounding confidence bar: when injecting the poj-bar-track HTML, "
        "place it on its own line at the very start of the response. "
        "In **Knowledge Audit** mode, you should also use these bars in the "
        "\"Confidence\" column of your summary table for each domain.\n"
        "7. **Diagnostic Codes (DTCs)**: Use standard **bold** text or `CODE` markers for DTCs. "
        "(Note: Frontend will automatically style valid DTCs (e.g., P0101) as pills—do not wrap them in HTML tags yourself).\n"
        "---\n\n"
        "### Key Principles\n\n"
        "- **Answer the actual question**: If asked \"how does X work\", explain how "
        "it works. If asked about a DTC, diagnose it. Match your response to the "
        "query type.\n"
        "- **Use retrieved context first**, but don't be paralyzed by gaps — "
        "apply engineering knowledge\n"
        "- **Egyptian market focus**: Nissan Sunny B17, Chery Tiggo 7, MG ZS, "
        "Toyota Corolla E210, Peugeot 301, Renault Logan\n"
        "- **Egyptian market realities** (apply to every recommendation):\n"
        "  - Most workshops use Launch X431, not OEM tools \u2014 always "
        "provide an X431-compatible procedure.\n"
        "  - Fuel quality varies \u2014 consider carbon buildup / injector "
        "fouling as higher-probability causes than in other markets.\n"
        "  - High ambient temps cause sensor drift on MAF, IAT, coolant.\n"
        "  - Parts sourcing is slow and expensive \u2014 confirm before replacing.\n"
        "'مركز صيانة معتمد' — not a brand name.\n"
        "- **Be helpful**: Even if context is limited, provide value based on "
        "automotive fundamentals\n"
        f"{history_block}"
    )

    # A3: DTC Prefix Decode Protocol \u2014 injected only for diagnostic intents
    if intent in (_IntentType.FAULT_DIAGNOSIS, _IntentType.KNOWLEDGE_AUDIT):
        system_prompt += _DTC_DECODE_BLOCK

    # A4: Sensor Grounding Rules \u2014 injected only for value-citing intents
    if intent in (_IntentType.FAULT_DIAGNOSIS, _IntentType.CATALOG_LOOKUP):
        system_prompt += _SENSOR_GROUNDING_BLOCK

    # 4. Multi-collection retrieval
    ranked_lists: list[list[NodeWithScore]] = []
    for cfg in _COLLECTION_CFG:
        try:
            store_kwargs: dict = {
                "aclient": client,
                "collection_name": cfg["name"],
                "enable_hybrid": cfg["enable_hybrid"],
            }
            if cfg["vector_name"] is not None:
                store_kwargs["vector_name"] = cfg["vector_name"]
            if cfg["sparse_vector_name"] is not None:
                store_kwargs["sparse_vector_name"] = cfg["sparse_vector_name"]

            vector_store = QdrantVectorStore(**store_kwargs)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            idx = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                embed_model=embed_model,
                storage_context=storage_context,
            )

            vehicle_filter = None if is_audit else _parse_vehicle_filter(car_context)

            # CHANGE 5: For HV/SRS, overlay a domain-tag filter on
            # pojehat_hybrid_v1 (existing collection — no new collections).
            if is_hv_srs and cfg["name"] == "pojehat_hybrid_v1":
                domain_f = _build_domain_filter(["hv_ev", "srs"])
                vehicle_filter = (
                    Filter(must=[vehicle_filter, domain_f])
                    if vehicle_filter
                    else domain_f
                )

            index_nodes: list[NodeWithScore] = []

            if vehicle_filter is not None:
                try:
                    retriever = idx.as_retriever(
                        similarity_top_k=effective_top_k,
                        vector_store_kwargs={"qdrant_filters": vehicle_filter}
                    )
                    index_nodes = await retriever.aretrieve(hyde_text)
                except Exception:
                    logger.info(
                        "Filter failed for %s, retrying unfiltered.", cfg["name"]
                    )
                    vehicle_filter = None

            if vehicle_filter is None or not index_nodes:
                index_nodes = await idx.as_retriever(
                    similarity_top_k=effective_top_k
                ).aretrieve(hyde_text)

            ranked_lists.append(index_nodes)
        except Exception as e:
            logger.warning("Retrieval failed for %s: %s", cfg["name"], e)

    if not ranked_lists:
        return "⚠️ تعذّر الاتصال بقاعدة المعلومات."

    # 5. RRF merge
    fused_nodes = _rrf_merge(ranked_lists)

    # 6. Score threshold gating
    passing_nodes = [
        n for n in fused_nodes if (n.score or 0.0) >= settings.RAG_SCORE_THRESHOLD
    ]
    if not passing_nodes:
        # Absolute empty guard
        if not fused_nodes:
            return "⚠️ لم يُعثر على بيانات كافية."
        passing_nodes = fused_nodes[:3]

    final_k = len(passing_nodes) if is_audit else settings.RAG_FINAL_K
    top_nodes = passing_nodes[:final_k]

    # Calculate retrieval-derived confidence score
    if is_audit and top_nodes:
        retrieval_metrics = _compute_retrieval_metrics(top_nodes)
        metrics_block = (
            "\n\n### Retrieval Metrics "
            "(GROUND TRUTH \u2014 report these exactly)\n\n"
        )
        metrics_block += (
            "| Source Document | Chunks | Avg RRF | Coverage % | Grounding Bar |\n"
        )
        metrics_block += "|---|---|---|---|---|\n"
        for source, m in retrieval_metrics.items():
            pct = m["coverage_pct"]
            bar = _generate_grounding_bar_html(int(pct))
            metrics_block += (
                f"| {source} | {m['chunk_count']} | {m['avg_rrf_score']} "
                f"| {pct}% | {bar.replace('|', '&#124;')} |\n"
            )
        # Add verbatim instructions with brand color codes for LLM to follow exactly
        metrics_block += (
            "\n**STRICT VERBATIM INSTRUCTION (NO MODIFICATIONS):** When building your "
            "domain table, you MUST copy the HTML from the 'Grounding Bar' column above "
            "EXACTLY as it is written. Do NOT change classes, do NOT add background styles, "
            "and do NOT invent your own HTML. Copy the full `<div>...</div>` into the "
            "'Confidence' column. This allows the system's CSS to style them correctly.\n"
            "\n**BRAND COLOR CODES (USE THESE ONLY):**\n"
            "- Green (80%+): #639922\n"
            "- Orange (50-79%): #ef9f27\n"
            "- Red (<50%): #e24b4a\n"
        )
        system_prompt += metrics_block

        # Audit queries use the average coverage_pct from metrics
        # (Boost slightly for audit broadness baseline)
        avg_pct = sum(m["coverage_pct"] for m in retrieval_metrics.values()) / len(retrieval_metrics)
        confidence_pct = min(100.0, max(0.0, avg_pct))
    elif top_nodes:
        # Diagnostic queries use normalized RRF score
        # (assuming Qdrant cosine similarity typically 0.5-0.9)
        avg_score: float = sum(n.score or 0.0 for n in top_nodes) / float(
            len(top_nodes)
        )
        # Scale 0.7-0.9 to 0-100% for display
        confidence_pct = min(100, max(0, int((avg_score - 0.5) * 200)))
    else:
        confidence_pct = 0

    # Final grounding bar for the top of the response
    bar_html = _generate_grounding_bar_html(int(confidence_pct))
    system_prompt += (
        "\n\n### MANDATORY: START your response with this exact grounding "
        "confidence bar:\n"
        f"{bar_html}\n\n"
    )

    # 7. LLM synthesis
    try:
        qa_template = _build_qa_template(system_prompt)
        synthesizer = get_response_synthesizer(
            llm=llm, text_qa_template=qa_template
        )
        response = await synthesizer.asynthesize(
            query=query, nodes=top_nodes
        )
        response_str = str(response).strip()
        
        # Ensure grounding bar (---) is ALWAYS the first line for non-audit queries
        # (Audit queries have their own special HTML bar)
        # REC-5: Safety gate — Python prepend guarantees it regardless of LLM output
        if is_hv_srs:
            # For HV/SRS, we want the safety warning, then the response (which starts with the bar)
            response_str = _HV_SRS_SAFETY_PREFIX + response_str

        # Ensure consistent spacing after the bar
        if response_str.startswith("<div"):
            # If the response starts with the bar, ensure there's a clear separation for what follows
            # if it's not already separated.
            pass

        return response_str
    except (RuntimeError, ValueError, UnexpectedResponse) as e:
        logger.error("RAG synthesis failure: %s", e)
        return f"RAG Engine Query Failure: {e}"
