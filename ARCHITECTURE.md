# Pojehat System Architecture

## Overview

Pojehat follows a stateless, modular architecture designed to transform colloquial automotive queries into expert-grounded diagnostic responses. The system utilizes a multi-stage pipeline that combines deterministic regional expertise with high-intelligence RAG retrieval.

## Diagnostic Pipeline Diagram

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'primaryColor': '#ffffff', 'edgeColor': '#cccccc', 'lineColor': '#cccccc', 'tertiaryColor': '#f9f9f9', 'fontFamily': 'Inter, sans-serif' }}}%%
graph TD
    A[HTTP Request /api/v1/diagnostics/ask] --> B{Intent Classification}
    B -->|SYSTEM_QUERY| C[Short-circuit Response]
    B -->|FAULT_DIAGNOSIS| D[HyDE Query Expansion]
    B -->|KNOWLEDGE_AUDIT| E[Multi-Collection Retrieval]
    D --> E
    E --> F[pojehat_hybrid_v1 + pojehat_obd_ecu_v1]
    F --> G[RRF Merge k=60]
    G --> H{Score Threshold >= 0.014}
    H -->|Pass| I[LLM Synthesis: Grok-4.1]
    H -->|Fail| J[Fallback: Generic Advice]
    I --> K[HTTP Response: Bilingual + Pills]
```

## VIN Decode: 3-Tier Enrichment Cascade

Pojehat implements a proprietary 3-tier orchestration for VIN decoding, optimized with a process-level LRU cache for high-frequency regional identify lookups.

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'fontFamily': 'Inter, sans-serif' }}}%%
sequenceDiagram
    participant User
    participant API as /api/v1/vin-decode
    participant Cache as LRU _VIN_CACHE
    participant T1 as Tier 1: Local WMI + WMI Table
    participant T2 as Tier 2: auto.dev Global
    participant T3 as Tier 3: NHTSA Public
    
    User->>API: POST {vin}
    API->>Cache: _vin_cache_get(vin)
    alt Cache Hit
        Cache-->>API: Return Cached Result
    else Cache Miss
        API->>T1: WMI Match (BMW, MG, Chery, etc.)
        alt T1 Success
            T1-->>API: Identity + Technical Brief
        else T1 Fail
            API->>T2: auto.dev VIN API
            alt T2 Success
                T2-->>API: Global Identity
            else T2 Fail
                API->>T3: NHTSA API
                T3-->>API: Identity Result
            end
        end
        API->>Cache: _vin_cache_set(vin, Result)
    end
    API-->>User: JSON Response (has_rag_followup: true)
```

### Tier 1: Local Identity (Instant, <1ms cache / <10ms table)

- Engine: Local _WMI_TABLE + VEHICLE_CONTEXT_MAP in vehicle_specs.py + Refactored MD Reference Corpus.
- Target: Priority Egyptian market models (Nissan, Peugeot, Toyota, Chery, MG) + Expanded VIN Logic (Hyundai, Honda, Toyota, Mercedes, Land Rover).
- Optimization: LRU Cache (500 entries) prevents redundant external API calls.

### Tier 2: Global Identity (Async, 400-800ms)

- Engine: auto.dev VIN API.
- Coverage: Global marques not covered by local priority tables.

### Tier 3: Public Fallback (Async, 1s+)

- Engine: NHTSA vPIC API.
- Role: Validates checksums and provides basic identity for North American and European imports.

## Technical Ingestion Pipeline (DBC & PDF)

The system supports high-fidelity ingestion of unstructured PDFs and structured DBC (CAN Database) files.

```mermaid
%%{init: {'theme': 'neutral', 'themeVariables': { 'primaryColor': '#ffffff', 'edgeColor': '#666666', 'fontFamily': 'Inter, sans-serif' }}}%%
graph LR
    A[Technical Sources] --> B{File Type}
    B -->|PDF| C[pymupdf4llm Parser]
    B -->|DBC| D[Custom Message Chunker]
    C --> E[LlamaIndex Document]
    D --> E
    E --> F[text-embedding-3-small]
    F --> G[Qdrant Vector Store]
    
    subgraph Collections
        G --> H[pojehat_hybrid_v1: Technical Reference Library (WMI/VIN/Manuals)]
        G --> I[pojehat_obd_ecu_v1: Protocol & Signal Data (DBC)]
    end
```

## Frontend Rendering: Double-Bubble Delivery

1. Bubble 1 (Instant): Renders identity and deterministic tech specs (Engine codes, Oil types).
2. Bubble 2 (Async): Triggered by has_rag_followup: true. Performs a surgical retrieval from obd_ecu_v1 to display wiring pinouts or TSB data.

## Security & Config

- CORS: Managed via ALLOWED_ORIGINS in .env.
- Statelessness: No server-side sessions; history and context are client-managed for maximum horizontal scalability.
