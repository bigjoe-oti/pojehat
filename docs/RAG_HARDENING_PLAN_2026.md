# Implementation Plan — RAG Hardening & Optimization (2026 Refactor)

**Project:** Pojehat AI Diagnostic Engine
**Version:** 2.0.0
**Date:** 2026-03-18
**Owner:** Engineering Team

---

## Executive Summary

This document outlines the comprehensive hardening and optimization strategy for the Pojehat RAG (Retrieval-Augmented Generation) engine. The current architecture leverages HyDE query expansion, multi-collection RRF retrieval, and score-threshold gating. This plan identifies gaps, proposes optimizations, and defines a phased rollout to achieve production-grade reliability and performance.

### Document Structure

- **Phase 0** — 6 confirmed bug fixes (100% COMPLETED ✅)
- **Phase 1-4** — 8 optimization initiatives (Next Milestone)

> **Priority Directive:** Phase 0 tasks were **foundational prerequisites**. They have been completed and verified to ensure a stable baseline for future optimizations.

---

## 1. Current Architecture Assessment

### 1.1 Existing Components

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| RAG Engine | [`src/domain/rag_engine.py`](src/domain/rag_engine.py:1) | ✅ Operational | HyDE, RRF, threshold gating |
| PDF Parser | [`src/domain/pdf_parser.py`](src/domain/pdf_parser.py:1) | ✅ Operational | Table-aware, caption detection |
| Web Ingester | [`src/services/web_ingester.py`](src/services/web_ingester.py:1) | ✅ Operational | Rate-limited, retry logic |
| Bulk Ingester | [`src/services/bulk_ingester.py`](src/services/bulk_ingester.py:1) | ✅ Operational | FCC ID scraping |
| API Routes | [`src/app/api/routes.py`](src/app/api/routes.py:1) | ✅ Operational | FastAPI endpoints |
| Config | [`src/core/config.py`](src/core/config.py:1) | ✅ Operational | Pydantic settings |

### 1.2 Architecture Strengths

1. **HyDE Query Expansion** — Bridges colloquial queries to OEM technical language
2. **Multi-Collection RRF** — Reciprocal Rank Fusion across `pojehat_hybrid_v1` and `pojehat_obd_ecu_v1`
3. **Score Threshold Gating** — Prevents low-quality context from reaching LLM
4. **Singleton Pattern** — LLM, embedder, and Qdrant client reused across requests
5. **Structured Fallback** — Graceful degradation when retrieval fails
6. **3-Layer VIN Enrichment** — Instant deterministic brief + Async RAG enrichment

### 1.3 Confirmed Bug Fixes (Phase 0 — COMPLETED ✅)

All foundational Phase 0 tasks have been successfully implemented and verified as of 2026-03-18.

| ID | Bug | Status | Severity | File(s) |
|----|-----|--------|----------|---------|
| **T1** | CORS wildcard + credentials conflict | ✅ Fixed | Critical | [`main.py`](src/app/main.py) |
| **T2** | RRF threshold calibrated for RRF | ✅ Fixed | Critical | [`config.py`](src/core/config.py) |
| **T3** | Settings mutation fix (Lifespan) | ✅ Fixed | Warning | [`main.py`](src/app/main.py) |
| **T4** | Non-blocking async upload logic | ✅ Fixed | Warning | [`routes.py`](src/app/api/routes.py) |
| **T5** | System prompt in `SYSTEM` role | ✅ Fixed | Warning | [`rag_engine.py`](src/domain/rag_engine.py) |
| **T6** | Qdrant startup health check | ✅ Fixed | High | [`main.py`](src/app/main.py) |
| **T7** | 3-Layer VIN enrichment implementation | ✅ Fixed | High | [`vehicle_specs.py`](src/domain/vehicle_specs.py) |

### 1.4 Identified Gaps & Technical Debt (Phase 1+)

| ID | Gap | Severity | Impact |
|----|-----|----------|--------|
| G01 | No query caching | HIGH | Redundant LLM calls for repeated queries |
| G02 | No retrieval telemetry | HIGH | Blind to RRF score distribution, gate failure rates |
| G03 | Hardcoded collection names | MEDIUM | Schema changes require code deploys |
| G04 | No async batch ingestion API | MEDIUM | Web UI cannot track ingestion progress |
| G05 | LLM fallback on timeout | MEDIUM | Single point of failure on OpenRouter |
| G06 | No query rewriting for Egyptian dialect | MEDIUM | HyDE helps but dialect normalization missing |
| G07 | Static RRF k=60 parameter | LOW | Not tuned per collection pair |
| G08 | No chunk-level metadata enrichment | LOW | Missing source page, section headers in context |

---

## 2. Optimization Priorities (Next Milestone)

### Priority Matrix

```
Impact
  ↑
  │  G01          G02
  │  Query Cache  Telemetry
  │  (High)       (High)
  │
  │  G05          G04
  │  Fallback     Batch API
  │
  │  G06   G03    G07  G08
  │  Dialect Collections  k-Tune  Metadata
  │
  └────────────────────────────→ Effort
```

### Success Metrics (KPIs)

| Metric | Baseline | Target | Measurement |
|--------|----------|--------|-------------|
| P95 Query Latency | ~8s | <3s | Prometheus histogram |
| Cache Hit Rate | 0% | >40% | Redis stats |
| Gate Failure Rate | Unknown | <5% | Telemetry dashboard |
| LLM Timeout Rate | Unknown | <1% | Error tracking |
| Retrieval Precision@20 | Unknown | >0.75 | Human eval dataset |

---

## 3. Technical Specifications

*(Details retained from V1.0 for Phase 1+ implementation)*

... [rest of the technical specs] ...

---

*Document Version: 2.1 | Last Updated: 2026-03-18*
*Phase 0 COMPLETED — System Base Hardened*
