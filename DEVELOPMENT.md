# Pojehat Development Guide

## Prerequisites

- **Python**: 3.13+
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Qdrant**: A running Qdrant Cloud cluster or local instance.
- **API Keys**: OpenRouter (LLM/Embeddings), auto.dev (VIN Tier 2).

## Setup

```bash
git clone <repository_url>
cd pojehat
uv sync
cp .env.example .env
# Open .env and populate the required keys below
```

## Environment Variables

| Variable | Requirement | Description |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | Required | Key for LLM routing and OpenAI embeddings. |
| `AUTO_DEV_API_KEY` | Required | Key for auto.dev global VIN decoding Tier 2. |
| `ALLOWED_ORIGINS` | Required | Comma-separated CORS origins (e.g. `http://localhost:3000`). |
| `QDRANT_URL` | Required | Your Qdrant Cloud cluster endpoint. |
| `QDRANT_API_KEY` | Required | Qdrant API Key / JWT. |

## Running Tier-1 Backend

Start the FastAPI server with hot-reload:
```bash
uvicorn src.app.main:app --reload --port 8000
```
- **Health Check**: `GET http://localhost:8000/health`
- **Swagger Docs**: `http://localhost:8000/docs`

## Frontend Development

The dashboard is built with Next.js and Tailwind CSS.
```bash
cd pojehat-web
npm install
npm run dev
```

### Visual Formatting Constraints
Frontend rendering depends on specific regex markers from the backend.
- **DTCs**: Valid DTC patterns (e.g. P0101) are automatically styled as pills by the frontend logic. Do NOT wrap them in HTML tags in the backend.
- **Part Numbers**: Prefix with `p/n` for automatic blue highlighting.
- **Grounding Bars**: Managed via `_generate_grounding_bar_html` in `rag_engine.py`. Current V2 style targets high contrast and `0.95em` typography.

## Data Ingestion

To ingest the core technical corpus, local PDFs, or the new VIN/WMI Reference Library:
```bash
# Ingest technical MD/PDF references in /md directory
# (Requires pymupdf4llm, llama-index-embeddings-openai)
python3 src/scripts/ingest_vins_md.py 
```

## Linting & Formatting

We enforce strict **Ruff** compliance. No legacy `os` modules; use `pathlib`.
```bash
# Check and fix linting
.venv/bin/python -m ruff check src/ --fix

# Format code
.venv/bin/python -m ruff format src/
```

## Critical Constraints

- **Statelessness**: NEVER add server-side session storage. 
- **Type Safety**: 100% type-hinted functions required (PEP 8 + Ruff).
- **VIN Logic**: Any changes to `decode_vin` must respect the 3-layer cascade in `vehicle_specs.py`.
- **CORS**: Avoid `"*"` in production; use specific origins in `.env`.
