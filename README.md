# Nexus — Enterprise AI Knowledge Base

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/FastAPI-0.135-green?style=for-the-badge&logo=fastapi" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react" />
  <img src="https://img.shields.io/badge/Qdrant-Vector%20DB-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Ollama-Local%20LLM-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

> **Nexus** is a highly secure, enterprise-grade, internal AI Knowledge Base platform. It enables organizations to securely ingest, process, index, and query massive volumes of internal documents using Retrieval-Augmented Generation (RAG) — entirely offline, with no data ever leaving the corporate network.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Module Deep Dive](#module-deep-dive)
- [Data Flow](#data-flow)
- [Installation & Setup](#installation--setup)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Access Control Matrix](#access-control-matrix)
- [Security & Compliance](#security--compliance)
- [Scripts & Utilities](#scripts--utilities)
- [Testing](#testing)
- [Frontend Overview](#frontend-overview)
- [Deployment](#deployment)
- [Roadmap & Future Enhancements](#roadmap--future-enhancements)
- [Contributing](#contributing)

---

## Overview

Modern enterprises generate vast amounts of internal knowledge — policy documents, HR manuals, engineering specs, spreadsheets, presentations, and more. Nexus transforms this scattered, static content into a dynamic, queryable AI-powered knowledge base.

Unlike cloud-based solutions, Nexus is designed from the ground up with **data sovereignty** as a first principle. It runs entirely within your internal network using local LLM inference via [Ollama](https://ollama.com/), a local speech-to-text engine ([Vosk](https://alphacephei.com/vosk/)), and a self-hosted vector database (Qdrant). Sensitive corporate data never transits an external network boundary — there are **no** Google Cloud, OpenAI, Anthropic, or other third-party SaaS dependencies in the runtime path.

Nexus enforces a multi-tiered **Role-Based Access Control (RBAC)** model, ensuring that employees can only retrieve answers from documents that their specific role and department explicitly authorize them to access. Every interaction is logged for compliance and audit purposes.

**Use Cases:**
- Enterprise internal Q&A (HR policies, legal, finance)
- Secure research assistant for regulated industries (healthcare, defense, finance)
- On-premise document intelligence for government and public sector
- Internal knowledge management for engineering and product teams

---

## Key Features

### Core AI Capabilities

- **Retrieval-Augmented Generation (RAG):** `sentence-transformers` embed document chunks into a Qdrant vector database. Queries are answered by retrieving the most semantically relevant chunks and passing them as context to the LLM, with strict grounding rules.
- **Anti-Hallucination Guardrails:** [`llm/prompt_builder.py`](llm/prompt_builder.py) injects a system prompt that forbids the LLM from drawing on knowledge outside the retrieved context, and instructs it to return a canned "I don't have that information" response when the retrieved chunks are insufficient.
- **Custom Q&A Override System:** Organizations can register canonical question-and-answer pairs through [`services/custom_qa_service.py`](services/custom_qa_service.py). Matches are detected with `RapidFuzz` and returned directly, bypassing the LLM entirely. Used for high-priority, policy-critical questions where determinism matters.
- **Multi-Format Document Ingestion:** Native extractors for PDF (with on-prem Tesseract OCR fallback for scanned pages), DOCX, XLSX/XLS, PPTX, plain images (PNG/JPG/TIFF), and plain text — all in [`ingestion/extractors/`](ingestion/extractors/).
- **Cross-Document Multi-Hop Retrieval:** When a chunk references an identifier (Roll No, Employee ID, Reg No, etc.) the engine optionally performs a second retrieval pass keyed on that identifier so answers can span multiple documents. See `_multi_hop_retrieval` in [`retrieval/query_engine.py`](retrieval/query_engine.py). Toggled by `MULTI_HOP_ENABLED`.
- **Page-Number Citations:** PDF chunks carry the originating page through to retrieval. Each query response returns a `citations` list of `{file, pages}` entries, rendered in the chat UI next to every source tag (e.g., `hr_policy.pdf · pp. 3–5, 7`).
- **History-Aware Re-Ranking:** The `_history_rerank` step in the query engine gives a light score boost to chunks whose text overlaps with terms from earlier conversation turns, keeping follow-up questions anchored to the same thread.

### Security & Access Control

- **Enterprise RBAC:** Role hierarchy `employee → manager → ceo → admin` defined in `core.security.RoleChecker.ROLE_HIERARCHY`. Each document is tagged with `allowed_roles`, `departments`, and `hierarchy`; retrieval filters enforce these at the Qdrant query level **and** at the application layer (`_enforce_role_access`).
- **Zero-Trust Defaults:** Documents are inaccessible to all users unless their role/department combination explicitly grants permission. There is no implicit sharing.
- **JWT Authentication with Token Blacklisting:** Two-token system (access + refresh). Logout pushes the JTI into Redis with TTL = remaining token life; every request checks the blacklist before proceeding.
- **IP Whitelisting Middleware:** [`api/middleware/ip_whitelist.py`](api/middleware/ip_whitelist.py) gates traffic at the network level when `IP_WHITELIST_ENABLED=true`.
- **Immutable Audit Logs:** Every query, document upload, and deletion is persisted to the SQLite `audit_logs` table via [`db/repositories/audit_repo.py`](db/repositories/audit_repo.py) — append-only, with user id, request id, IP, and timing.
- **Fail-Safe Cache Behavior:** Redis outages never crash the request path. [`cache/cache_service.py`](cache/cache_service.py) logs and degrades silently; rate limiting falls open, token blacklist fails closed.

### User Experience

- **Speech-to-Text (STT):** Local Vosk engine wrapped by [`services/stt_service.py`](services/stt_service.py). Two endpoints: `POST /api/v1/stt/transcribe` for buffered audio, and a `WS /api/v1/stt/stream` WebSocket for live, low-latency streaming. The frontend pre-warms a WebSocket on page load so the first utterance has no cold-start latency.
- **Modern React Frontend:** React 18 + Vite, Framer Motion animations, react-three-fiber landing scene, dark theme, and a typewriter-style answer renderer ([`components/TypewriterMessage.jsx`](frontend/src/components/TypewriterMessage.jsx)) that displays sources with collapsed page ranges.
- **Redis Caching:** Query results (answer + sources + citations + role union) cached by normalized question hash. Cache hits short-circuit the entire pipeline.
- **Offline / Edge Ready:** The full stack — embedding, LLM, STT — runs on-prem with zero internet egress.
- **Conversational Context:** The frontend captures the last 6 messages (≈3 turns) and sends them as `conversation_history` in the query payload. The API schema validates and truncates the list, the prompt builder injects a `PREVIOUS CONVERSATION` block, and the query engine applies the history-aware re-ranking described above.

---

## System Architecture

Nexus is a **FastAPI Python backend** and a **React frontend**, connected via a JSON REST API (plus a WebSocket for STT streaming).

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Frontend (Vite)                         │
│   Query/Chat  │  Upload  │  Documents  │  Users  │  Audit  │  Q&A    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP/REST + WS  (JWT in header or query)
┌────────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend  (/api/v1)                       │
│  auth │ query │ ingest │ admin │ departments │ custom_qa │ stt       │
│   Middleware: RequestLoggingMiddleware, IPWhitelistMiddleware, CORS  │
└───┬───────────┬──────────────┬───────────────┬────────────────────┘
    │           │              │               │
    ▼           ▼              ▼               ▼
┌───────┐  ┌────────┐   ┌──────────┐   ┌──────────────┐
│  /db  │  │ /core  │   │  /cache  │   │  /services   │
│SQLite │  │Security│   │  Redis   │   │Business Logic│
│Models │  │Config  │   │ Caching  │   │Auth/STT/QA/  │
│Repos  │  │Logger  │   │BlackList │   │Ingest/Query  │
└───────┘  └────────┘   └──────────┘   └──────┬───────┘
                                              │
               ┌──────────────────────────────┤
               │                              │
    ┌──────────▼──────────┐       ┌───────────▼─────────────┐
    │    /ingestion        │       │      /retrieval         │
    │  Extractor Registry  │       │   Qdrant Vector Store   │
    │  Smart Chunker       │       │   Query Engine (ANN)    │
    │  Embedder            │       │   RBAC + Multi-Hop      │
    │  Page-Marker Tagger  │       │   History Reranker      │
    └──────────────────────┘       └────────────┬────────────┘
                                                │
                                    ┌───────────▼─────────────┐
                                    │         /llm             │
                                    │   PromptBuilder          │
                                    │   Ollama Client          │
                                    └─────────────────────────┘
```

### Request Lifecycle (Query Path)

1. **User** submits a question via the React UI (text or microphone stream).
2. **FastAPI** authenticates the JWT, applies request logging + IP whitelist middleware.
3. **`QueryService.ask`** ([services/query_service.py](services/query_service.py)) checks the per-user rate limit in Redis.
4. **`QueryEngine.query`** ([retrieval/query_engine.py](retrieval/query_engine.py)):
   - Checks Custom Q&A (fuzzy match via `RapidFuzz`) — exact match returns immediately.
   - Checks Redis query cache — hit returns instantly.
   - Embeds the question with `sentence-transformers`.
   - Searches Qdrant with RBAC filter (`allowed_roles`, `departments`, `topic_ancestors`).
   - Re-ranks: name-aware boost → conversation-history boost → relative score floor.
   - Re-enforces RBAC at the application layer as defense in depth.
   - Optionally executes a multi-hop search keyed on identifiers extracted from the first-hop chunks.
5. **`PromptBuilder.build_rag_prompt`** assembles the system rules, prior conversation, and labeled context.
6. **`OllamaClient`** generates the answer.
7. The result + structured `citations` (file + page numbers) is cached in Redis and returned.
8. The full interaction is recorded in the `audit_logs` table.

### Document Ingestion Lifecycle

1. **Admin uploads** a file via the Upload page with `allowed_roles`, `department`, and `hierarchy`.
2. The file is dispatched through `ExtractorRegistry` ([ingestion/pipeline.py](ingestion/pipeline.py)) to the matching extractor.
3. PDF pages are stamped with `<<NEXUS_PAGE:N>>` markers; the pipeline carries the current page across chunks and stores `pages: List[int]` per chunk in the Qdrant payload.
4. `SmartChunker` produces paragraph- or semantic-aware chunks with configurable overlap.
5. Each chunk is embedded and upserted to Qdrant with the full metadata payload (text, source_file, doc_id, chunk_index, departments, hierarchy, allowed_roles, topic_id, topic_ancestors, pages).
6. The document is recorded in the `documents` SQLite table; the ingestion event is logged to `audit_logs`.

---

## Technology Stack

### Backend

| Component | Technology | Purpose |
|---|---|---|
| Runtime | Python 3.10+ | Core backend language |
| Web Framework | FastAPI 0.135 | Async REST API, OpenAPI docs |
| ASGI Server | Uvicorn 0.41 | Production async server |
| ORM | SQLAlchemy 2.0 | Database models and queries |
| Relational DB | SQLite (via SQLAlchemy) | Users, documents, audit logs, custom Q&A |
| Migrations | Alembic 1.18 | Schema migrations |
| Vector DB | Qdrant 1.17 | ANN vector search with payload filtering |
| Cache / Sessions | Redis 7.2 | Query cache, rate limiting, token blacklist |
| Embeddings | sentence-transformers 5.2 | Dense text embeddings (`all-MiniLM-L6-v2` default) |
| Local LLM | Ollama 0.6 | On-prem LLM provider |
| PDF Extraction | pdfplumber, pdfminer.six, pypdf | Native PDF text extraction |
| OCR | pytesseract | Local OCR fallback for scanned PDFs and images (no cloud API) |
| Word Docs | python-docx 1.2 | `.docx` parsing |
| Spreadsheets | openpyxl 3.1, xlrd 2.0 | `.xlsx` / `.xls` parsing |
| Presentations | python-pptx 1.0 | `.pptx` parsing |
| Unstructured Fallback | unstructured 0.21 | Multi-format parser |
| Auth | python-jose 3.5 | JWT creation & validation |
| Password Hashing | bcrypt 5.0 | Credential storage |
| Rate Limiting | slowapi 0.1 + limits 5.8 | Per-user request limits |
| Data Validation | pydantic 2.12 | Request/response schemas |
| Logging | structlog 25.5 | Structured logs |
| ML Framework | torch 2.10, transformers 5.2 | Model inference |
| DL Optimization | accelerate 1.13, optimum 2.1 | Optimized inference |
| STT | Vosk (local) | Speech-to-text |

### Frontend

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | React 18 | Component model |
| Build Tool | Vite 7 | Dev server + bundler |
| Animations | Framer Motion 12, GSAP 3 | Page and UI transitions |
| 3D Scene | three.js + @react-three/fiber + @react-three/drei | Landing-page particle scene |
| Routing | react-router-dom 7 | Client-side SPA routing |
| HTTP Client | axios 1.13 | API client with JWT interceptors |
| Drag-and-Drop | react-dropzone 15 | Document upload UI |
| Toasts | react-hot-toast 2 | Notifications |
| Icons | react-icons 5 | Iconography |
| Styling | Plain CSS per-component | Scoped styles next to each page/component |

### Infrastructure (Self-Hosted)

| Service | Default Port | Purpose |
|---|---|---|
| FastAPI | 8000 | Backend REST + WS API |
| React Dev Server | 5173 | Frontend development |
| Qdrant | 6333 (HTTP) / 6334 (gRPC) | Vector database |
| Redis | 6379 | Cache and session store |
| Ollama | 11434 | Local LLM inference |

---

## Project Structure

```
nexus/
│
├── api/                          # FastAPI application layer
│   ├── main.py                   # App factory, lifespan, middleware, router mounting
│   ├── dependencies.py           # Shared DI: get_db, get_current_user, get_request_id, get_client_ip
│   ├── middleware/
│   │   ├── logging.py            # Structured per-request logging
│   │   └── ip_whitelist.py       # CIDR allowlist enforcement
│   ├── routes/                   # Route handlers grouped by domain
│   │   ├── auth.py               # /auth: login, logout, refresh, me
│   │   ├── query.py              # /query: ask, history, debug
│   │   ├── ingest.py             # /documents: upload, list, delete, prune, clear-all
│   │   ├── admin.py              # /admin: users, audit-logs, health
│   │   ├── departments.py        # /departments: list, create, delete
│   │   ├── custom_qa.py          # /custom-qa: CRUD + toggle
│   │   └── stt.py                # /stt: transcribe (POST), status, stream (WebSocket)
│   └── schemas/
│       ├── request.py            # LoginRequest, QueryRequest, ConversationTurn, CreateUserRequest, ...
│       └── response.py           # APIResponse envelope, QueryResponse, Citation, ...
│
├── cache/
│   ├── redis_client.py           # Connection pool + health check
│   └── cache_service.py          # QueryCache, TokenBlacklist, RateLimit (all fail-safe)
│
├── core/
│   ├── config.py                 # pydantic-settings Settings + sub-settings groups
│   ├── security.py               # PasswordHandler, TokenHandler, RoleChecker
│   ├── exceptions.py             # GreenBaseException hierarchy + ErrorCode enum
│   └── logger.py                 # structlog setup + TimedOperation context manager
│
├── db/
│   ├── base.py                   # SQLAlchemy declarative base + engine + session helpers
│   ├── models.py                 # All ORM models in one file
│   │                             #   Department, User, Document, TopicNode,
│   │                             #   AuditLog, RefreshToken, CustomQA
│   └── repositories/             # Repository pattern (one file per aggregate)
│       ├── user_repo.py
│       ├── doc_repo.py
│       ├── dept_repo.py
│       ├── topic_repo.py
│       ├── custom_qa_repo.py
│       └── audit_repo.py
│
├── frontend/                     # React 18 + Vite SPA
│   ├── public/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── index.css
│   │   ├── context/
│   │   │   └── AuthContext.jsx
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── QueryPage.jsx        # Main chat UI
│   │   │   ├── UploadPage.jsx       # Drag-and-drop document upload
│   │   │   ├── DocumentsPage.jsx    # List + manage uploaded docs
│   │   │   ├── UsersPage.jsx        # User management (admin)
│   │   │   ├── DepartmentsPage.jsx  # Department management
│   │   │   ├── CustomQAPage.jsx     # Custom Q&A CRUD
│   │   │   ├── AuditPage.jsx        # Audit log viewer
│   │   │   └── HistoryPage.jsx      # Personal query history
│   │   ├── components/
│   │   │   ├── Layout.jsx           # App shell
│   │   │   ├── Sidebar.jsx          # Nav with role-gated items
│   │   │   ├── RouteGuards.jsx      # ProtectedRoute / RoleRoute
│   │   │   ├── PageTransition.jsx   # Framer Motion page wrapper
│   │   │   ├── GlowOrb.jsx          # Decorative orb
│   │   │   └── TypewriterMessage.jsx # AI message bubble + source/citation rendering
│   │   ├── hooks/
│   │   │   ├── useSttStreaming.js   # Mic + WebSocket lifecycle for live STT
│   │   │   └── useChatPersistence.js # localStorage save/restore for chat threads
│   │   ├── utils/
│   │   │   ├── audio.js             # PCM/WAV helpers, resampling, normalization
│   │   │   └── auth.js              # Valid-access-token check
│   │   ├── landing/
│   │   │   └── Scene3D.jsx          # three.js particle landing scene
│   │   └── services/
│   │       └── api.js               # Axios instance + per-domain API wrappers (queryAPI, sttAPI, ...)
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── ingestion/
│   ├── pipeline.py               # ExtractorRegistry + IngestionPipeline orchestrator
│   ├── chunker.py                # SmartChunker (paragraph or semantic strategy)
│   ├── embedder.py               # SentenceTransformer singleton
│   └── extractors/
│       ├── base.py               # BaseExtractor ABC + ExtractionResult dataclass
│       ├── pdf.py                # pdfplumber + pytesseract OCR fallback; injects page markers
│       ├── docx.py
│       ├── excel.py              # openpyxl / xlrd
│       ├── pptx.py
│       ├── image.py              # Preprocess + pytesseract OCR
│       └── txt.py
│
├── llm/
│   ├── base.py                   # LLMClient ABC + LLMResponse dataclass
│   ├── ollama_client.py          # HTTP client with prewarm + retries
│   └── prompt_builder.py         # RAG prompt, no-results prompt, disambiguation prompt
│
├── retrieval/
│   ├── vector_store.py           # Qdrant client wrapper, SearchResult (with .pages)
│   └── query_engine.py           # Full RAG flow + helpers: name-rerank, history-rerank,
│                                 #   multi-hop, RBAC re-enforcement, citation builder
│
├── scripts/
│   ├── create_admin.py           # Bootstrap the first admin user
│   ├── reset_data.py             # DESTRUCTIVE: wipe DB + Qdrant (dev only)
│   ├── migrate_db.py             # Run Alembic migrations
│   ├── migrate_dept.py           # One-off department-shape migration
│   ├── verify_custom_qa.py       # Validate custom Q&A repository contents
│   └── auto_docstring.py         # Repo maintenance helper
│
├── services/
│   ├── auth_service.py           # Login, logout, refresh, password ops
│   ├── ingest_service.py         # Coordinates the ingestion pipeline + DB updates
│   ├── query_service.py          # Rate limit + RAG + audit logging
│   ├── custom_qa_service.py      # Fuzzy-match lookup for custom Q&A pairs
│   ├── topic_service.py          # Topic-tree clustering for filtering and grouping
│   └── stt_service.py            # Vosk wrapper (transcribe + streaming)
│
├── tests/                        # pytest suite (pure-unit, no external services)
│   ├── conftest.py               # Shared fixtures + minimal env bootstrap
│   ├── test_prompt_builder.py    # RAG / summary / disambiguation prompts
│   ├── test_chunker.py           # SmartChunker paragraph splits + overlap
│   ├── test_cache_keys.py        # Redis key derivation + namespacing
│   ├── test_query_engine_helpers.py # RBAC, score floor, multi-hop IDs,
│   │                                #   name-rerank, history-rerank, citations
│   └── test_exceptions.py        # HTTP status mapping + error details
│
├── pytest.ini                    # pytest configuration (testpaths, asyncio mode)
│
├── models/                       # On-disk model files (embedding model + Vosk STT models)
├── uploads/                      # Uploaded documents (gitignored)
├── logs/                         # Structured logs (gitignored)
├── data/                         # Local data artifacts
│
├── docker-compose.yml            # Qdrant + Redis services
├── requirements.txt              # Pinned dependency list (with test deps)
├── req.txt                       # Pinned dependency list (runtime-focused snapshot)
└── README.md
```

---

## Module Deep Dive

### `/api` — FastAPI Application Layer

Entry point for all client interactions. Structured around FastAPI routers in [`api/routes/`](api/routes/):

- **`auth.py`** — `POST /auth/login` (issues JWT access + refresh), `POST /auth/logout` (blacklists the JTI), `POST /auth/refresh`, `GET /auth/me`.
- **`query.py`** — `POST /query/ask` (the core RAG endpoint), `GET /query/history`, plus admin-only `POST /query/debug/retrieve` and `GET /query/debug/contains` for inspecting retrieval.
- **`ingest.py`** — `POST /documents/upload`, `GET /documents/`, `DELETE /documents/{id}`, `DELETE /documents/clear-all`, `POST /documents/prune-missing`.
- **`admin.py`** — User CRUD, audit log viewer, system health.
- **`departments.py`** — Department list / create / delete.
- **`custom_qa.py`** — Custom Q&A pair CRUD + toggle.
- **`stt.py`** — `POST /stt/transcribe` (buffered), `GET /stt/status`, `WS /stt/stream` (live streaming with prewarm support).

Dependencies in [`api/dependencies.py`](api/dependencies.py) provide `get_db`, `get_current_user` (with role + department + hierarchy), `get_request_id`, and `get_client_ip`.

Middleware (registered in [`api/main.py`](api/main.py)):
- `RequestLoggingMiddleware` — structured per-request log line with timing
- `IPWhitelistMiddleware` — CIDR allowlist when `IP_WHITELIST_ENABLED=true`
- `CORSMiddleware` — origins from `CORS_ORIGINS`
- Two exception handlers convert `GreenBaseException` → typed JSON error envelope; everything else → a generic 500 without stack traces.

---

### `/ingestion` — Document Processing Pipeline

Sequential processor: raw file → extracted text → chunks → vectors in Qdrant.

**Extractors** ([ingestion/extractors/](ingestion/extractors/)) all inherit `BaseExtractor`:

| Extractor | Libraries | Special Handling |
|---|---|---|
| [`pdf.py`](ingestion/extractors/pdf.py) | `pdfplumber`, `pytesseract` | Falls back to local `pytesseract` OCR for scanned pages; injects `<<NEXUS_PAGE:N>>` markers so the pipeline can attach page numbers to each chunk. |
| [`docx.py`](ingestion/extractors/docx.py) | `python-docx` | Body text, headers, footers, tables. |
| [`excel.py`](ingestion/extractors/excel.py) | `openpyxl`, `xlrd` | Iterates sheets; cell values serialized with sheet context. |
| [`pptx.py`](ingestion/extractors/pptx.py) | `python-pptx` | Slides, text frames, notes, table shapes. |
| [`image.py`](ingestion/extractors/image.py) | `pytesseract`, `Pillow` | Preprocess (grayscale, contrast, sharpen, upscale) then OCR. |
| [`txt.py`](ingestion/extractors/txt.py) | stdlib | UTF-8 / Latin-1 fallback. |

**Chunker** ([ingestion/chunker.py](ingestion/chunker.py)) — `SmartChunker` supports two strategies (selected by `CHUNK_STRATEGY`):

1. **`paragraph`** — paragraph-aware sliding window with sentence-boundary fallback for oversized paragraphs and configurable token overlap.
2. **`semantic`** — embed each sentence and start a new chunk when the cosine similarity to the running chunk vector drops below `SEMANTIC_SIM_THRESHOLD`.

**Embedder** ([ingestion/embedder.py](ingestion/embedder.py)) — Lazy-loaded `SentenceTransformer` singleton; default `all-MiniLM-L6-v2` (384-dim).

**Page tagging** — The pipeline ([ingestion/pipeline.py](ingestion/pipeline.py)) walks all chunks in order, carries the "current page" forward across chunks, strips the marker, and stores `pages: List[int]` on the Qdrant payload.

---

### `/retrieval` — Vector Search Engine

**`vector_store.py`** — Qdrant wrapper. Each point payload contains:

```json
{
  "text": "The original chunk text...",
  "source_file": "550e8400-..._HR_Policy.pdf",
  "doc_id": "doc-uuid",
  "chunk_index": 12,
  "departments": ["human_resources"],
  "hierarchy": 1,
  "allowed_roles": ["admin", "manager", "employee"],
  "word_count": 187,
  "topic_id": "topic-uuid",
  "topic_ancestors": ["root-id", "ancestor-id"],
  "pages": [3, 4]
}
```

`SearchResult` normalizes those fields, including `.pages`, so nothing else in the codebase touches Qdrant types directly.

**`query_engine.py`** — Full RAG flow:

1. Optional LLM-driven query rewrite (`QUERY_REWRITE_ENABLED`).
2. Embed the question.
3. `vector_store.search` with the RBAC filter (`allowed_roles` MatchAny + optional `departments` + optional `topic_ancestors`).
4. Name-aware re-ranking for "who is …" style questions.
5. **History-aware re-ranking** — extracts 4+ char tokens from prior turns and boosts overlapping chunks.
6. Relative score floor (`SCORE_RELATIVE_THRESHOLD * top_score`, with a hard `MIN_SCORE_THRESHOLD`).
7. Application-layer RBAC re-enforcement (defense in depth).
8. Optional multi-hop retrieval keyed on extracted identifiers (Roll No, ID, Reg No).
9. Build the prompt within `CONTEXT_CHAR_BUDGET`.
10. Generate via the configured LLM client.
11. Aggregate `citations` (file + sorted, de-duplicated pages) and cache the result.

---

### `/llm` — Language Model Orchestration

**`prompt_builder.py`** — Builds the RAG prompt with:
- A strict system prompt forbidding outside knowledge.
- Numbered, source-labelled context blocks (`[Source 1: file.pdf]`).
- Optional `PREVIOUS CONVERSATION` block populated from `conversation_history` (entries longer than 300 chars are truncated).
- The user question.

Also exposes `build_no_results_response`, `build_disambiguation_response`, `build_query_focus_prompt`, and `build_summary_prompt`.

**`ollama_client.py`** — HTTP client for `http://OLLAMA_HOST` with prewarm, retries, and configurable generation params (`OLLAMA_NUM_PREDICT`, `OLLAMA_TEMPERATURE`, `OLLAMA_NUM_CTX`, `OLLAMA_TOP_P/TOP_K/REPEAT_PENALTY`).

---

### `/services` — Business Logic

- **`auth_service.py`** — bcrypt password check, JWT issuance, refresh-token rotation, JTI blacklisting.
- **`query_service.py`** — Rate-limit + invoke `query_engine.query` + audit log (success / rate-limited / error paths).
- **`ingest_service.py`** — Coordinates upload → extraction → chunking → embedding → Qdrant upsert → SQLite record, with cleanup on partial failure.
- **`custom_qa_service.py`** — `RapidFuzz` lookup against the active custom Q&A pairs; threshold via `CUSTOM_QA_SIMILARITY_THRESHOLD`.
- **`topic_service.py`** — Builds and resolves the topic tree used for optional topic-scoped retrieval.
- **`stt_service.py`** — Vosk singleton supporting both one-shot transcription (`transcribe(bytes)`) and live WebSocket streaming (`create_recognizer(sample_rate)`). The model loads once on import; the `/stt/stream` route exposes a `prewarm=1` query param to warm the WebSocket path without sending audio.

---

### `/core` — Configuration & Security

**`config.py`** — `pydantic-settings`-based `Settings` class, all values overridable via environment variables (see [Configuration](#configuration)).

**`security.py`** — `PasswordHandler` (bcrypt), `TokenHandler` (`create_access_token`, `create_refresh_token`, `decode_token`), `RoleChecker` (`ROLE_HIERARCHY = {employee:1, manager:2, ceo:3, admin:4}`, `has_role`, `has_any_role`, `require_admin`, `require_roles`).

**`exceptions.py`** — `GreenBaseException` hierarchy mapped to typed HTTP statuses: `AuthenticationError → 401`, `AuthorizationError → 403`, `IngestionError → 422`, `RecordNotFoundError → 404`, `RateLimitExceededError → 429`, etc. All errors carry a machine-readable `ErrorCode` enum value.

**`logger.py`** — `structlog` configuration plus a `TimedOperation` context manager for emitting consistent latency logs.

---

### `/db` — Database Layer

ORM models all live in [`db/models.py`](db/models.py):

- **`Department`** — Department directory.
- **`User`** — Email, bcrypt password, roles (JSON list), department FK, hierarchy level, active flag.
- **`Document`** — Filename, original filename, file type, size, allowed_roles, departments, hierarchy, status, ingestion timing.
- **`TopicNode`** — Topic-tree node for topic-scoped retrieval.
- **`AuditLog`** — Append-only record of every query and admin action.
- **`RefreshToken`** — Refresh-token metadata for rotation tracking.
- **`CustomQA`** — Canonical question/answer pairs with priority and toggle flag.

Repositories in [`db/repositories/`](db/repositories/) wrap each aggregate (`user_repo`, `doc_repo`, `dept_repo`, `topic_repo`, `custom_qa_repo`, `audit_repo`). Migrations are managed via Alembic; the runner script is [`scripts/migrate_db.py`](scripts/migrate_db.py).

---

## Data Flow

### Query Flow (Text)

```
User types question
       │
       ▼
QueryPage → POST /api/v1/query/ask {question, conversation_history?, ...}
       │
       ▼
JWT auth → IPWhitelist → RequestLogging
       │
       ▼
QueryService.ask(...)
   ├─ Rate-limit check (Redis)
   └─ QueryEngine.query(...)
        ├─ Custom Q&A fuzzy match  ──► hit → return canonical answer
        ├─ Redis cache lookup      ──► hit → return cached payload
        ├─ Embed question (SentenceTransformer)
        ├─ Qdrant ANN search (RBAC filter applied at the DB level)
        ├─ Name-rerank + History-rerank
        ├─ Score-floor + Application-layer RBAC re-enforcement
        ├─ Optional multi-hop retrieval on extracted identifiers
        ├─ PromptBuilder.build_rag_prompt (history + numbered context)
        ├─ LLMClient.generate(prompt)  ──► Ollama
        ├─ Build citations [{file, pages: sorted, deduped}]
        ├─ Cache in Redis (answer + sources + citations + role union)
        └─ Audit-log the request
       │
       ▼
Frontend renders answer + sources tagged with collapsed page ranges
```

### Ingestion Flow

```
Admin uploads file (UploadPage)
       │
       ▼
POST /api/v1/documents/upload (multipart: file + metadata)
       │
       ▼
IngestionService → IngestionPipeline.ingest(...)
   ├─ Validate (size, extension)
   ├─ Register Document row in SQLite (status=processing)
   ├─ ExtractorRegistry.get(...) → extractor.extract(...)
   ├─ TopicService.build_for_document (best-effort)
   ├─ SmartChunker.chunk(...)
   ├─ Tag chunks with pages (carry-forward of <<NEXUS_PAGE:N>>)
   ├─ Embedder.embed_batch(...)
   ├─ Qdrant upsert (batches of 100) with full payload incl. pages
   ├─ Update Document row (status=completed, chunk count, timing)
   └─ Audit log
```

---

## Installation & Setup

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Qdrant | Latest | Run via Docker (recommended) |
| Redis | 7+ | Run via Docker (recommended) |
| Ollama | Latest | With at least one model pulled |
| Tesseract OCR | 4.1+ | Required for OCR fallback in PDF/image extraction |
| Docker (optional) | Latest | Used by `docker-compose.yml` for Qdrant + Redis |

### 1. Start Infrastructure Services

The bundled `docker-compose.yml` brings up Qdrant + Redis with persistent volumes and health checks:

```bash
docker compose up -d
```

Or run them manually:

```bash
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z qdrant/qdrant

docker run -d -p 6379:6379 redis:7-alpine

ollama serve
ollama pull phi3:mini    # matches the default OLLAMA_MODEL; swap for any supported model
```

### 2. Clone the Repository

```bash
git clone https://github.com/hackerxhari/nexus.git
cd nexus
```

### 3. Backend Setup

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Linux/macOS
# venv\Scripts\activate           # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Install Tesseract system dependency (Ubuntu/Debian example)
sudo apt-get install tesseract-ocr

# Create your .env (see Configuration below for full variable list)
$EDITOR .env

# Initialize the database
python -m scripts.reset_data     # destructive: wipes DB + Qdrant collection

# Create the first admin user
python -m scripts.create_admin

# Start the FastAPI server
uvicorn api.main:app --reload --port 8000
```

The API is now available at `http://localhost:8000`. Interactive Swagger docs are at `http://localhost:8000/docs` when `APP_ENV=development`.

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend is now available at `http://localhost:5173`.

---

## Configuration

Nexus loads its configuration from environment variables (or a `.env` file at the project root). Variable names match the settings in [`core/config.py`](core/config.py). The most relevant variables:

```env
# ── App ────────────────────────────────────────────────────────
APP_NAME=Nexus
APP_VERSION=1.0.0
APP_ENV=development                # development | staging | production
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# ── Security ───────────────────────────────────────────────────
SECRET_KEY=change-this-in-production-minimum-32-characters-long
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256
BCRYPT_ROUNDS=12

# ── Database ───────────────────────────────────────────────────
DATABASE_URL=sqlite:///./nexus.db

# ── Qdrant ─────────────────────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=nexus_kb
QDRANT_VECTOR_SIZE=384

# ── Redis ──────────────────────────────────────────────────────
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_QUERY_CACHE_TTL=3600         # seconds
REDIS_EMBEDDING_CACHE_TTL=86400
REDIS_MAX_CONNECTIONS=10

# ── LLM ────────────────────────────────────────────────────────
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=phi3:mini
OLLAMA_TIMEOUT=120
OLLAMA_PREWARM=true
OLLAMA_NUM_PREDICT=256
OLLAMA_TEMPERATURE=0.1
OLLAMA_NUM_CTX=2048

# ── Embeddings ─────────────────────────────────────────────────
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_BATCH_SIZE=32

# ── Ingestion ──────────────────────────────────────────────────
MAX_FILE_SIZE_MB=50
ALLOWED_FILE_TYPES=pdf,docx,txt,png,jpg,jpeg,tiff,pptx,ppt,xlsx,xls
CHUNK_SIZE=400                     # tokens
CHUNK_OVERLAP=50                   # tokens
CHUNK_STRATEGY=semantic            # paragraph | semantic
SEMANTIC_SIM_THRESHOLD=0.55
UPLOAD_DIR=uploads

# ── Retrieval ──────────────────────────────────────────────────
RETRIEVAL_TOP_K=8
RETRIEVAL_SCORE_THRESHOLD=0.25
SCORE_RELATIVE_THRESHOLD=0.65
MIN_SCORE_THRESHOLD=0.30
MULTI_HOP_ENABLED=false
TOPIC_FILTER_ENABLED=false
QUERY_REWRITE_ENABLED=false
NAME_RERANK_ENABLED=true
CONTEXT_CHAR_BUDGET=9000

# ── Custom Q&A ─────────────────────────────────────────────────
CUSTOM_QA_ENABLED=true
CUSTOM_QA_SIMILARITY_THRESHOLD=0.60

# ── Conversation ───────────────────────────────────────────────
CONVERSATION_HISTORY_TURNS=1

# ── Network Security ───────────────────────────────────────────
IP_WHITELIST_ENABLED=false
ALLOWED_IP_RANGES=127.0.0.1/32,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# ── Speech-to-Text ─────────────────────────────────────────────
VOSK_ENABLED=true
VOSK_LANGUAGE=en
VOSK_MODEL_PATH=models/vosk-model-en-in-0.5

# ── Rate Limiting ──────────────────────────────────────────────
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_BURST=5

# ── Logging ────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_FILE=logs/nexus.log
```

Generate a strong `SECRET_KEY` with `openssl rand -hex 32`. In production, `SECRET_KEY` must not contain the substring `change-this` and `DEBUG` must be `false` — the settings validator enforces both.

---

## API Reference

All endpoints are prefixed with `/api/v1`. All non-public endpoints require a valid JWT in the `Authorization: Bearer <token>` header.

### Authentication — `/api/v1/auth`

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/auth/login` | Authenticate user, receive access + refresh tokens | Public |
| `POST` | `/auth/logout` | Revoke current token (blacklist its JTI) | Required |
| `POST` | `/auth/refresh` | Exchange a refresh token for a new access token | Public |
| `GET` | `/auth/me` | Return the authenticated user's profile | Required |

### Query — `/api/v1/query`

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/query/ask` | Run a RAG query | Employee+ |
| `GET` | `/query/history` | Get the caller's query history | Employee+ |
| `POST` | `/query/debug/retrieve` | Inspect retrieved chunks without LLM generation | Admin |
| `GET` | `/query/debug/contains` | Check whether a phrase exists in a stored document's chunks | Admin |

**`POST /api/v1/query/ask` — request:**
```json
{
  "question": "What is the company's remote work policy?",
  "department_filter": null,
  "bypass_cache": false,
  "conversation_history": [
    {"role": "user", "content": "What is the leave policy?"},
    {"role": "assistant", "content": "Employees get 20 paid days per year..."}
  ]
}
```

**Response (`APIResponse[QueryResponse]`):**
```json
{
  "success": true,
  "request_id": "req-abc123",
  "data": {
    "answer": "Employees may work remotely up to three days per week with manager approval...",
    "sources": ["HR_Remote_Work_Policy_2024.pdf"],
    "citations": [
      {"file": "HR_Remote_Work_Policy_2024.pdf", "pages": [3, 4]}
    ],
    "chunks_retrieved": 4,
    "cache_hit": false,
    "performance": {
      "response_time_ms": 842.3,
      "embedding_time_ms": 12.4,
      "retrieval_time_ms": 31.7,
      "llm_time_ms": 760.1
    },
    "rate_limit": {
      "remaining": 7,
      "limit": 10,
      "reset_in_seconds": 42
    }
  }
}
```

### Document Management — `/api/v1/documents`

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/documents/upload` | Upload and ingest a document | Employee+ |
| `GET` | `/documents/` | List documents the caller can see | Employee+ |
| `DELETE` | `/documents/{doc_id}` | Delete a single document + its vectors | Admin |
| `DELETE` | `/documents/clear-all` | Delete every document (DESTRUCTIVE) | Admin |
| `POST` | `/documents/prune-missing` | Drop DB rows whose underlying file no longer exists | Admin |

### Speech-to-Text — `/api/v1/stt`

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/stt/transcribe` | Transcribe a single audio upload | Employee+ |
| `GET` | `/stt/status` | Whether STT is initialized and which language is active | Employee+ |
| `WS` | `/stt/stream` | Live streaming transcription (partials + finals); supports a `prewarm=1` query param to warm the model without sending audio | Employee+ (JWT in `?token=`) |

### Administration

User and audit endpoints are under `/api/v1/admin`; departments and custom Q&A have their own top-level prefixes.

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/admin/users` | Create a user | Admin |
| `GET` | `/admin/users` | List users | Admin / Manager (dept-scoped) |
| `PATCH` | `/admin/users/{user_id}/roles` | Update a user's roles | Admin |
| `PATCH` | `/admin/users/{user_id}/deactivate` | Deactivate a user | Admin |
| `DELETE` | `/admin/users/{user_id}` | Delete a user | Admin |
| `GET` | `/admin/audit-logs` | View audit log | Admin / CEO / Manager (dept-scoped) |
| `GET` | `/admin/health` | Service health check | Admin |
| `GET` | `/departments` | List departments | Authenticated |
| `POST` | `/departments` | Create a department | Admin |
| `DELETE` | `/departments/{dept_id}` | Delete a department | Admin |
| `POST` | `/custom-qa/` | Create a custom Q&A pair | Admin |
| `GET` | `/custom-qa/` | List custom Q&A pairs | Admin |
| `PUT` | `/custom-qa/{qa_id}` | Update a pair | Admin |
| `DELETE` | `/custom-qa/{qa_id}` | Delete a pair | Admin |
| `PATCH` | `/custom-qa/{qa_id}/toggle` | Toggle active flag | Admin |

Full interactive docs are available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` when `APP_ENV=development`.

---

## Access Control Matrix

Nexus implements a hierarchical RBAC model. The hierarchy levels (from `RoleChecker.ROLE_HIERARCHY`) are: `employee=1`, `manager=2`, `ceo=3`, `admin=4`. `has_role` accepts a role if the user's highest level is ≥ the required level; `require_admin` and `require_roles` enforce exact-role gates.

| Action | Admin | CEO | Manager | Employee |
|---|:---:|:---:|:---:|:---:|
| Ask Questions | ✅ | ✅ | ✅ | ✅ |
| Upload Documents | ✅ | ✅ | ✅ | ✅ |
| Delete Documents | ✅ | ❌ | ❌ | ❌ |
| View Own Query History | ✅ | ✅ | ✅ | ✅ |
| View All Query History | ✅ | ✅ | Dept. only | ❌ |
| View Audit Logs | ✅ | ✅ | Dept. only | Self only |
| Create Users | ✅ | ❌ | ❌ | ❌ |
| Edit User Roles | ✅ | ❌ | ❌ | ❌ |
| Deactivate Users | ✅ | ❌ | ❌ | ❌ |
| Manage Custom Q&A | ✅ | ❌ | ❌ | ❌ |
| Manage Departments | ✅ | ❌ | ❌ | ❌ |
| Multi-Hop Debug Endpoints | ✅ | ❌ | ❌ | ❌ |
| System Health | ✅ | ❌ | ❌ | ❌ |

> **"Dept. only"** means the action is allowed but scoped to the caller's own department.

**Document-Level Access:** Beyond the role gate, each document carries an explicit `allowed_roles` list, a `departments` list, and a `hierarchy` integer. A user only sees a chunk if (a) any of their roles is in `allowed_roles`, (b) the user is global (`admin`/`ceo`) OR their department is in `departments` (or `departments` is empty), and (c) `document.hierarchy ≤ user.hierarchy`. This is enforced both at the Qdrant query level and re-enforced application-side in `_enforce_role_access`.

---

## Security & Compliance

### Authentication
- **JWT (HS256 by default).** Short-lived access tokens (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 15) and long-lived refresh tokens (`REFRESH_TOKEN_EXPIRE_DAYS`, default 7).
- **Token Blacklisting.** Logout pushes the JTI into Redis with TTL = remaining token life. Every authenticated request checks the blacklist; on Redis failure, the check **fails closed** (request denied) to prevent privilege escalation.
- **Password Security.** bcrypt with configurable rounds (`BCRYPT_ROUNDS`, default 12). Plain text passwords are never stored or logged.

### Network Security
- **IP Whitelisting** via `IP_WHITELIST_ENABLED` + `ALLOWED_IP_RANGES` (CIDR list). Requests from outside the allowlist are rejected before auth.
- **CORS** strictly limited to origins in `CORS_ORIGINS`.
- **HTTPS.** In production, terminate TLS at a reverse proxy (nginx, Caddy). The backend assumes it's behind a trusted proxy and reads client IPs from `X-Forwarded-For` via `get_client_ip`.

### Data Security
- **Zero-Trust Vector Retrieval.** RBAC filters are applied at the Qdrant query level (Qdrant returns nothing the user can't see), then re-enforced application-side. The LLM never receives unauthorized chunks.
- **No External Data Transmission.** All LLM inference (Ollama), embedding (sentence-transformers), and OCR (pytesseract) run locally. No document content, queries, or responses are sent to any third-party API.
- **Append-Only Audit Logs.** Every query and admin write is recorded with user id, IP, request id, timing breakdown, and result status.

### Compliance Considerations
- Immutable audit log supports GDPR Article 30 (records of processing) and ISO 27001 access-control requirements.
- Department + hierarchy isolation supports need-to-know data classification policies.
- Fully offline operation meets data-residency requirements for regulated industries.

---

## Scripts & Utilities

| Script | Usage | Description |
|---|---|---|
| `scripts/create_admin.py` | `python -m scripts.create_admin` | Interactively create the first admin user. Required for initial setup. |
| `scripts/reset_data.py` | `python -m scripts.reset_data` | **Destructive.** Drops + recreates SQLite tables and deletes the Qdrant collection. Dev only. |
| `scripts/migrate_db.py` | `python -m scripts.migrate_db` | Run pending Alembic migrations. Use in production for schema updates. |
| `scripts/migrate_dept.py` | `python -m scripts.migrate_dept` | One-off helper that backfills department shape changes. |
| `scripts/verify_custom_qa.py` | `python -m scripts.verify_custom_qa` | Validates the contents of the custom Q&A repository. |
| `scripts/auto_docstring.py` | `python -m scripts.auto_docstring` | Repo maintenance: add file-level docstrings to source files. |

---

## Testing

Nexus ships a `pytest` suite that exercises the pure, deterministic parts of the system — no Qdrant, no Redis, no Ollama, no GPU required. Tests run in well under two minutes on a laptop.

### Running the suite

```bash
# Install test deps (already pinned in requirements.txt)
pip install pytest pytest-asyncio pytest-cov

# Run everything
pytest

# Verbose
pytest -v

# Only one module
pytest tests/test_prompt_builder.py -v

# With coverage report
pytest --cov=. --cov-report=term-missing
```

`pytest.ini` configures `testpaths=tests`, `asyncio_mode=auto`, and silences benign deprecation warnings. `tests/conftest.py` injects the minimum environment (`SECRET_KEY`, `APP_ENV=development`, in-memory SQLite) so that `core.config.Settings` loads without a `.env` file.

### What is covered

| File | What it asserts |
|---|---|
| [`tests/test_prompt_builder.py`](tests/test_prompt_builder.py) | The RAG prompt includes the question, every chunk, and numbered `[Source N: file]` labels; `user_name` is optional; `conversation_history` injects a `PREVIOUS CONVERSATION` block; long turns are truncated to 300 chars + `...`; empty history is omitted; the no-results response is identical regardless of input (so RBAC-blocked vs genuinely-empty queries are indistinguishable); the disambiguation response lists up to 5 sources; the summary and query-focus prompts contain their inputs. |
| [`tests/test_chunker.py`](tests/test_chunker.py) | `SmartChunker` returns empty for empty input; rejects `chunk_overlap >= chunk_size`; produces sequential `chunk_index`es; drops chunks below `min_chunk_size`; propagates metadata; `_clean_text` normalises whitespace; `_split_sentences` splits on `.!?`; `_add_overlap` repeats the last N words of the previous chunk; `TextChunk.word_count` / `char_count` are accurate. |
| [`tests/test_cache_keys.py`](tests/test_cache_keys.py) | Query cache key is stable, case-insensitive, whitespace-trimmed, varies with `topic_id` and `department`, and is namespaced under `nexus:query:`; blacklist / rate-limit / session keys follow their expected `nexus:*` patterns. |
| [`tests/test_query_engine_helpers.py`](tests/test_query_engine_helpers.py) | `_clean_source_name` strips UUID prefixes (case-insensitive); `_extract_name_query` recognises common "who is …" prefixes; `_filter_results_by_score` retains the top-scored chunk; `_extract_cross_doc_identifiers` finds Roll No / Employee ID / Reg No patterns and returns empty when none match; `_enforce_role_access` lets admins bypass department, blocks unauthorised roles, requires department match for non-globals, blocks documents above the user's hierarchy, and allows documents with no department restriction; `_cache_roles_ok` allows entries with no restriction and requires at least one role match; `_rerank_results_by_name_query` boosts chunks containing all name parts and leaves short queries alone; `_history_rerank` is a no-op on empty history and re-orders chunks that overlap with prior-turn terms; `_build_citations` aggregates and de-duplicates pages per source, strips UUID prefixes, and skips sources not in the `used_sources` list. |
| [`tests/test_exceptions.py`](tests/test_exceptions.py) | Every exception class maps to its expected HTTP status (`AuthenticationError → 401`, `AuthorizationError → 403`, `RecordNotFoundError → 404`, `FileTooLargeError → 422`, `RateLimitExceededError → 429`, `QueryFailedError → 500`, …); `ErrorCode` values are preserved through the hierarchy; `details` propagate. |

### Current results

```
============================ 74 passed in 8s ============================
```

### Design notes

- All tests are **unit tests** with no I/O. They run identically on CI, on a developer laptop with no infrastructure, and inside a clean Docker image.
- The retrieval-engine tests use a small `FakeResult` duck-type stand-in for `vector_store.SearchResult`, which keeps the suite independent from Qdrant.
- Tests exist not just for happy paths but specifically guard the **RBAC enforcement**, **fail-closed cache lookups**, and **page-citation aggregation** code paths — the parts where a regression would have a security or correctness impact.

---

## Frontend Overview

The frontend is a React 18 + Vite SPA with client-side routing via `react-router-dom`.

### Pages

| Page | Route | Description |
|---|---|---|
| `LoginPage.jsx` | `/login` | Animated login form. Stores JWT and redirects to the query page. |
| `QueryPage.jsx` | `/query` | Main chat surface — text input, microphone button, typewriter answer rendering with collapsed page-range citations. |
| `UploadPage.jsx` | `/upload` | Drag-and-drop document upload with RBAC tagging. |
| `DocumentsPage.jsx` | `/documents` | List and manage ingested documents (delete for admins). |
| `UsersPage.jsx` | `/users` | User management (admin). |
| `DepartmentsPage.jsx` | `/departments` | Department CRUD. |
| `CustomQAPage.jsx` | `/custom-qa` | Admin-only canonical Q&A management. |
| `AuditPage.jsx` | `/audit` | Audit log viewer, filterable by date / user / event. |
| `HistoryPage.jsx` | `/history` | The current user's own query history. |

### Components / Hooks / Utils

- [`components/TypewriterMessage.jsx`](frontend/src/components/TypewriterMessage.jsx) — AI message bubble with word-by-word typewriter effect and source-tag list. Renders citations as `file.pdf · pp. 1–3, 7`, collapsing contiguous page ranges automatically.
- [`components/Layout.jsx`](frontend/src/components/Layout.jsx), [`Sidebar.jsx`](frontend/src/components/Sidebar.jsx), [`RouteGuards.jsx`](frontend/src/components/RouteGuards.jsx), [`PageTransition.jsx`](frontend/src/components/PageTransition.jsx), [`GlowOrb.jsx`](frontend/src/components/GlowOrb.jsx) — App shell, nav, route protection, transitions.
- [`hooks/useSttStreaming.js`](frontend/src/hooks/useSttStreaming.js) — Owns the microphone + WebSocket lifecycle (prewarm, start, stop, silence detection). Pre-warms on page load when STT is available.
- [`hooks/useChatPersistence.js`](frontend/src/hooks/useChatPersistence.js) — Saves the current chat thread to `localStorage` per-user so messages survive a page refresh.
- [`utils/audio.js`](frontend/src/utils/audio.js) — Pure PCM/WAV helpers: mono mix, resampling, normalization, WAV encoding, RMS, duration formatting.
- [`utils/auth.js`](frontend/src/utils/auth.js) — Reads and validates the JWT from `localStorage`, returning `null` if expired.
- [`services/api.js`](frontend/src/services/api.js) — Axios instance with JWT interceptor + per-domain wrappers (`queryAPI`, `sttAPI`, `authAPI`, …).
- [`landing/Scene3D.jsx`](frontend/src/landing/Scene3D.jsx) — three.js particle scene used on the landing/login screen.

### State Management

Global authentication state (current user, role, JWT) lives in `AuthContext` (React Context API). The axios client (`services/api.js`) automatically attaches the JWT, intercepts 401 responses, attempts a refresh, and retries the original request.

### Build

```bash
cd frontend
npm run dev        # development (Vite, hot reload at :5173)
npm run build      # production build → frontend/dist
npm run preview    # serve the production build locally
```

---

## Deployment

### Docker Compose

The bundled `docker-compose.yml` brings up Qdrant and Redis with persistent volumes and health checks. The FastAPI backend and React frontend are run separately during development (and behind your own reverse proxy in production).

```yaml
# ─────────────────────────────────────────────
# Nexus — Infrastructure Services
# Starts Qdrant (vector DB) and Redis (cache).
# The FastAPI backend and React frontend are
# run separately during development.
#
# Usage:
#   docker compose up -d          # start both services in background
#   docker compose down           # stop and remove containers
#   docker compose down -v        # also wipe persistent volumes
# ─────────────────────────────────────────────

version: "3.9"

services:

  # ── Qdrant Vector Database ──────────────────
  qdrant:
    image: qdrant/qdrant:latest
    container_name: nexus-qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"   # HTTP REST API
      - "6334:6334"   # gRPC API
    volumes:
      - qdrant_storage:/qdrant/storage
    environment:
      QDRANT__LOG_LEVEL: INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 10s

  # ── Redis Cache & Session Store ─────────────
  redis:
    image: redis:7-alpine
    container_name: nexus-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 30s
      timeout: 5s
      retries: 5
      start_period: 5s

# ── Named Volumes ───────────────────────────
volumes:
  qdrant_storage:
    driver: local
  redis_data:
    driver: local

```

### Recommended Production Architecture

```
Internet → Firewall/VPN → nginx (TLS) → FastAPI (Uvicorn, N workers)
                                       ↓
                               Qdrant (internal)
                               Redis (internal)
                               Ollama (GPU host, internal)
```

For high availability, Qdrant supports distributed mode and replication, Redis can be deployed as a cluster, and FastAPI workers can be horizontally scaled behind a load balancer.

---

## Roadmap & Future Enhancements

The following capabilities are partially shipped or planned. Items marked **Planned** are **not yet production-ready** and should not be relied upon in regulated deployments.

### Conversational Context

Nexus already accepts the last 6 messages (≈3 turns) as `conversation_history` on every query. They are validated by `ConversationTurn`, injected into the prompt as a `PREVIOUS CONVERSATION` block, and used by the history-aware re-ranking step.

| Milestone | Status | Description |
|---|:---:|---|
| Frontend context capture | ✅ Done | `getConversationHistory` in `QueryPage.jsx` sends the last 6 messages |
| API schema (`ConversationTurn`, `conversation_history`) | ✅ Done | Validated Pydantic model with a hard cap of 6 entries |
| Prompt injection (`PREVIOUS CONVERSATION` block) | ✅ Done | History inserted into the RAG prompt before the question |
| History-aware retrieval re-ranking | ✅ Done | `_history_rerank` boosts chunks whose text overlaps with prior-turn terms |
| Page-number citations in source UI | ✅ Done | `citations: List[{file, pages}]` returned from the API and rendered with collapsed page ranges |
| Server-side session persistence | ⏳ Planned | Store conversation turns in Redis keyed by `session_id`, surviving reloads and devices |
| Per-user conversation thread management | ⏳ Planned | Named threads (ChatGPT-style) stored in SQLite and browsable from the UI |
| Admin visibility into user sessions | ⏳ Planned | Extend audit log with `session_id` for compliance tracing |
| History summarisation | ⏳ Planned | Summarise older turns instead of hard-truncating, preserving long-running context |

**Current limitation:** History is persisted only in the browser's `localStorage`. Clearing storage, opening a private tab, or querying from a second device starts an independent session.

### Other Planned Features

- **Document Versioning.** Track multiple versions of the same document; pin or auto-resolve to latest.
- **Streaming LLM Responses.** Stream tokens to the frontend over Server-Sent Events instead of waiting for the full response.
- **Multi-Language Support.** Multilingual `sentence-transformers` for non-English corpora.
- **Plugin / Tool Calling.** Allow the LLM to invoke internal tools (e.g., fetch a live HR record, run a calculation) when retrieved context is insufficient.
- **Granular Document Expiry.** Auto-retire documents after a configurable TTL and prompt uploaders to refresh.

---

## Contributing

Contributions are welcome.

1. Fork the repository and create a feature branch (`git checkout -b feature/your-feature`).
2. Follow PEP 8 for Python. Use `black` for formatting and `flake8` for linting.
3. Document new functionality with concise docstrings and inline comments where the *why* is non-obvious.
4. Update this README and any relevant docstrings for new features.
5. Open a Pull Request with a clear description of the change and its motivation.

### Development Setup

```bash
pip install -r requirements.txt
pip install black flake8

flake8 . --max-line-length=100 --exclude=venv,__pycache__
black . --line-length=100
```

---

## License

This project is licensed under the MIT License.

---

## Author

**hackerxhari** — [github.com/hackerxhari](https://github.com/hackerxhari)

---

<p align="center">
  Built for enterprises that take data privacy seriously.
</p>
