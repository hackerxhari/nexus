# 🧠 Nexus — Enterprise AI Knowledge Base

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

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Technology Stack](#-technology-stack)
- [Project Structure](#-project-structure)
- [Module Deep Dive](#-module-deep-dive)
- [Data Flow](#-data-flow)
- [Installation & Setup](#-installation--setup)
- [Configuration](#-configuration)
- [API Reference](#-api-reference)
- [Access Control Matrix](#-access-control-matrix)
- [Security & Compliance](#-security--compliance)
- [Scripts & Utilities](#-scripts--utilities)
- [Frontend Overview](#-frontend-overview)
- [Deployment](#-deployment)
- [Contributing](#-contributing)

---

## 🌐 Overview

Modern enterprises generate vast amounts of internal knowledge — policy documents, HR manuals, engineering specs, spreadsheets, presentations, and more. Nexus transforms this scattered, static content into a dynamic, queryable AI-powered knowledge base.

Unlike cloud-based solutions, Nexus is designed from the ground up with **data sovereignty** as a first principle. It runs entirely within your internal network using local LLM inference (via [Ollama](https://ollama.com/) or [AirLLM](https://github.com/lyogavin/airllm)), local speech-to-text engines (Vosk/Moonshine), and self-hosted vector databases (Qdrant). Sensitive corporate data never transits an external network boundary.

Nexus enforces a multi-tiered **Role-Based Access Control (RBAC)** model, ensuring that employees can only retrieve answers from documents that their specific role and department explicitly authorize them to access. Every interaction is logged for compliance and audit purposes.

**Use Cases:**
- Enterprise internal Q&A (HR policies, legal, finance)
- Secure research assistant for regulated industries (healthcare, defense, finance)
- On-premise document intelligence for government and public sector
- Internal knowledge management for engineering and product teams

---

## 🌟 Key Features

### Core AI Capabilities
- **Retrieval-Augmented Generation (RAG):** State-of-the-art `sentence-transformers` embed document chunks into a scalable Qdrant vector database. Queries are answered by retrieving the most semantically relevant chunks and passing them as context to the LLM.
- **Anti-Hallucination Guardrails:** The prompt builder injects strict system instructions that forbid the LLM from generating answers not grounded in the retrieved context, with explicit source citations in every response.
- **Custom Q&A Override System:** Organizations can inject high-priority, canonical question-and-answer pairs directly into Nexus. These bypass LLM generation entirely, guaranteeing absolute factual accuracy for critical, frequently-asked questions (e.g., "What is our parental leave policy?").
- **Multi-Modal Document Ingestion:** Automatically extracts and processes text from PDFs (including OCR fallback for scanned images using Tesseract and Google Vision API), Word Documents (`.docx`), Excel Spreadsheets (`.xlsx`), PowerPoints (`.pptx`), and plain text files.

### Security & Access Control
- **Enterprise RBAC:** Multi-tiered access control with a hierarchy of Admin → CEO → Manager → Employee roles. Each document is tagged with allowed roles and departments at ingestion time; retrieval filters enforce these permissions at the vector database level.
- **Zero-Trust Defaults:** Documents are inaccessible to all users unless a role explicitly grants permission. There is no implicit sharing.
- **JWT Authentication with Token Blacklisting:** Secure login flow using JSON Web Tokens. Tokens are revoked on logout or role deactivation via Redis, preventing session replay attacks.
- **IP Whitelisting:** The backend API can be locked down to specific corporate subnet ranges, preventing unauthorized network-level access.
- **Immutable Audit Logs:** Every query, document upload, and deletion is permanently logged asynchronously to the relational database (`SQLite` via `SQLAlchemy`), providing a full audit trail for compliance.

### User Experience
- **Speech-to-Text (STT) Integration:** Native integration with local STT engines (Vosk/Moonshine) allows users to verbally query the knowledge base using their microphone — no cloud transcription service required.
- **Modern React Frontend:** A sleek, dark-mode UI built with React 18 and Vite, featuring Framer Motion animations, an intuitive chat interface, and a full administrative dashboard.
- **Redis Caching:** LLM responses and frequently accessed data are cached in Redis to dramatically reduce latency for repeated queries and to support rate limiting per user.
- **Offline / Edge Ready:** The entire stack — from embedding to LLM inference to speech recognition — can run on-premise without any internet connectivity.

---

## 🏗️ System Architecture

Nexus is cleanly separated into a **FastAPI Python backend** and a **React frontend**, connected via a RESTful JSON API. The backend itself is divided into well-defined, independently testable modules.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        React Frontend (Vite)                         │
│   Chat UI  │  Admin Dashboard  │  Document Manager  │  User Manager  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / REST (JWT-authenticated)
┌────────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Backend  (/api)                          │
│   Auth Router  │  Query Router  │  Admin Router  │  Ingestion Router  │
│                       Middleware (RBAC, Rate Limiting)               │
└───┬───────────┬──────────────┬───────────────┬────────────────────┘
    │           │              │               │
    ▼           ▼              ▼               ▼
┌───────┐  ┌────────┐   ┌──────────┐   ┌──────────────┐
│  /db  │  │ /core  │   │  /cache  │   │  /services   │
│SQLite │  │Security│   │  Redis   │   │Business Logic│
│Models │  │Config  │   │ Caching  │   │Auth, STT, Q&A│
└───────┘  └────────┘   └──────────┘   └──────┬───────┘
                                               │
               ┌───────────────────────────────┤
               │                               │
    ┌──────────▼──────────┐       ┌────────────▼────────────┐
    │    /ingestion        │       │      /retrieval          │
    │  Document Extractors │       │   Qdrant Vector Store    │
    │  Semantic Chunker    │       │   Query Engine (ANN)     │
    │  Sentence Embedder   │       │   RBAC Filters           │
    └──────────────────────┘       └────────────┬────────────┘
                                               │
                                   ┌────────────▼────────────┐
                                   │         /llm             │
                                   │   Prompt Builder         │
                                   │   Ollama Client          │
                                   │   AirLLM Client          │
                                   └─────────────────────────┘
```

### Request Lifecycle (Query Path)

1. **User** submits a question via the React UI (text or speech).
2. **FastAPI** authenticates the JWT, verifies the user's role against `RoleChecker`, and checks the Redis cache for a matching response.
3. **Cache Miss:** The `QueryEngine` in `/retrieval` embeds the query using `sentence-transformers`, applies hard RBAC filters (role + department) as Qdrant payload filters, and executes an Approximate Nearest Neighbor (ANN) search.
4. Retrieved context chunks are re-ranked and passed to the **`PromptBuilder`** in `/llm`, which constructs a structured prompt containing the system rules, context, and user query.
5. The prompt is sent to the configured **LLM provider** (Ollama or AirLLM) for generation.
6. The response, with source citations, is **cached in Redis** and returned to the user.
7. The entire interaction is **logged asynchronously** to the audit database.

### Document Ingestion Lifecycle

1. **User uploads** a document via the Admin UI with metadata (allowed roles, department tags, sensitivity level).
2. The file is routed to the appropriate **extractor** (`pdf_extractor`, `docx_extractor`, `xlsx_extractor`, `pptx_extractor`) based on MIME type.
3. Extracted text is passed to the **`chunker.py`** which splits it into semantically meaningful chunks with configurable overlap to preserve context across chunk boundaries.
4. Each chunk is passed to the **`embedder.py`** which generates a dense vector representation using `SentenceTransformers`.
5. Chunks and their vectors are **upserted into Qdrant** with rich metadata payloads (source file, page number, allowed roles, department, sensitivity).
6. The ingestion event is **logged** to the audit repository.

---

## 🛠️ Technology Stack

### Backend

| Component | Technology | Purpose |
|---|---|---|
| Runtime | Python 3.10+ | Core backend language |
| Web Framework | FastAPI 0.135 | Async REST API, OpenAPI docs |
| ASGI Server | Uvicorn 0.41 | Production-grade async server |
| ORM | SQLAlchemy 2.0 | Database models and queries |
| Relational DB | SQLite (via SQLAlchemy) | User, department, and audit data |
| Vector Database | Qdrant 1.17 | Scalable ANN vector search with metadata filtering |
| Cache / Sessions | Redis 7.2 | Response caching, rate limiting, token blacklisting |
| Embeddings | sentence-transformers 5.2 | Dense text embeddings (`all-MiniLM-L6-v2` default) |
| Local LLM | Ollama 0.6 | On-premise LLM inference (Llama 3, Mistral, etc.) |
| Alternative LLM | AirLLM 2.11 | Memory-efficient local LLM inference |
| PDF Extraction | pdfplumber, pdfminer.six, pypdf | Native text extraction from PDFs |
| OCR | pytesseract, Google Cloud Vision | Text extraction from scanned/image PDFs |
| Word Docs | python-docx 1.2 | `.docx` file parsing |
| Spreadsheets | openpyxl 3.1, xlrd 2.0 | `.xlsx`/`.xls` parsing |
| Presentations | python-pptx 1.0 | `.pptx` parsing |
| Unstructured | unstructured 0.21 | Multi-format document parsing fallback |
| Auth | python-jose 3.5 | JWT creation and validation |
| Password Hashing | bcrypt 5.0 | Secure credential storage |
| Rate Limiting | slowapi 0.1, limits 5.8 | Per-user API rate limiting |
| Data Validation | pydantic 2.12 | Request/response schema validation |
| Logging | structlog 25.5 | Structured, machine-readable logging |
| ML Framework | torch 2.10, transformers 5.2 | Model inference backbone |
| NLP | spacy 3.8 | Text preprocessing and analysis |
| Deep Learning | accelerate 1.13, optimum 2.1 | Optimized model inference |

### Frontend

| Component | Technology | Purpose |
|---|---|---|
| UI Framework | React 18 | Component-based UI |
| Build Tool | Vite | Lightning-fast dev server and bundler |
| Animations | Framer Motion | Page transitions and UI animations |
| Routing | React Router Dom | Client-side SPA routing |
| Styling | CSS Modules / Global CSS | Scoped component styles |

### Infrastructure (Self-Hosted)

| Service | Default Port | Purpose |
|---|---|---|
| FastAPI | 8000 | Backend REST API |
| React Dev Server | 5173 | Frontend development |
| Qdrant | 6333 | Vector database |
| Redis | 6379 | Cache and session store |
| Ollama | 11434 | Local LLM inference |

---

## 📁 Project Structure

```
nexus/
│
├── api/                          # FastAPI application layer
│   ├── main.py                   # App factory, middleware registration, router mounting
│   ├── dependencies.py           # Shared DI: get_db, get_current_user, get_redis
│   ├── middleware/               # Custom ASGI middleware (logging, CORS, IP whitelist)
│   ├── routers/                  # Route handlers grouped by domain
│   │   ├── auth.py               # POST /login, POST /logout, POST /refresh
│   │   ├── query.py              # POST /query (main RAG endpoint), GET /history
│   │   ├── ingestion.py          # POST /documents/upload, DELETE /documents/{id}
│   │   ├── admin.py              # User CRUD, department management
│   │   └── qa.py                 # Custom Q&A pair management
│   └── schemas/                  # Pydantic request/response models
│       ├── user.py               # UserCreate, UserResponse, TokenResponse
│       ├── query.py              # QueryRequest, QueryResponse, SourceCitation
│       └── document.py           # DocumentUpload, DocumentResponse
│
├── cache/                        # Caching layer
│   ├── redis_client.py           # Redis connection factory and health check
│   └── cache_service.py          # Cache get/set/invalidate helpers, TTL management
│
├── core/                         # Application core: config, security, exceptions
│   ├── config.py                 # Settings loaded from .env via pydantic-settings
│   ├── security.py               # JWT creation/validation, RoleChecker dependency
│   ├── exceptions.py             # Custom HTTP exceptions (NexusAuthError, etc.)
│   └── logging.py                # structlog configuration and processors
│
├── db/                           # Database layer
│   ├── base.py                   # SQLAlchemy declarative base, engine setup
│   ├── models/                   # ORM model definitions
│   │   ├── user.py               # User, Role, Department models
│   │   ├── document.py           # DocumentRecord model (metadata only)
│   │   └── audit.py              # AuditLog model
│   └── repositories/             # Data access layer (Repository Pattern)
│       ├── user_repo.py          # CRUD for users and role assignments
│       ├── document_repo.py      # Document metadata CRUD
│       ├── qa_repo.py            # Custom Q&A pair CRUD
│       └── audit_repo.py         # Append-only audit log writes
│
├── frontend/                     # React 18 + Vite frontend
│   ├── public/                   # Static assets (favicon, manifest)
│   ├── src/
│   │   ├── main.jsx              # React entry point
│   │   ├── App.jsx               # Root component, router setup
│   │   ├── context/              # React Context providers
│   │   │   └── AuthContext.jsx   # Authentication state and JWT management
│   │   ├── pages/                # Top-level route pages
│   │   │   ├── LoginPage.jsx     # Auth form with animated transitions
│   │   │   ├── ChatPage.jsx      # Main Q&A interface with voice support
│   │   │   ├── AdminPage.jsx     # User and department management dashboard
│   │   │   └── DocumentsPage.jsx # Document upload and management UI
│   │   ├── components/           # Reusable UI components
│   │   │   ├── ChatMessage.jsx   # Message bubble with source citations
│   │   │   ├── DocumentUpload.jsx # Drag-and-drop file uploader
│   │   │   ├── UserTable.jsx     # Admin user list with role editor
│   │   │   └── VoiceInput.jsx    # Microphone STT integration
│   │   └── api/                  # Typed API client wrappers
│   │       └── client.js         # Axios instance with JWT interceptors
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── ingestion/                    # Document processing pipeline
│   ├── pipeline.py               # Orchestrates extractor → chunker → embedder
│   ├── extractors/               # File-type-specific text extractors
│   │   ├── base_extractor.py     # Abstract base class for all extractors
│   │   ├── pdf_extractor.py      # pdfplumber + pytesseract OCR fallback
│   │   ├── docx_extractor.py     # python-docx text and table extraction
│   │   ├── xlsx_extractor.py     # openpyxl sheet and cell extraction
│   │   └── pptx_extractor.py     # python-pptx slide text extraction
│   ├── chunker.py                # Semantic sliding-window chunker with overlap
│   └── embedder.py               # SentenceTransformer embedding wrapper
│
├── llm/                          # LLM orchestration layer
│   ├── base_client.py            # Abstract LLM client interface
│   ├── ollama_client.py          # Ollama HTTP API client with streaming support
│   ├── airllm_client.py          # AirLLM memory-efficient inference client
│   └── prompt_builder.py         # Context merging, system prompt injection, citation formatting
│
├── retrieval/                    # Vector search and retrieval layer
│   ├── vector_store.py           # Qdrant collection management, upsert, delete
│   └── query_engine.py           # Query embedding, ANN search, RBAC filter application, re-ranking
│
├── scripts/                      # Administrative CLI utilities
│   ├── create_admin.py           # Bootstrap the first SuperAdmin user
│   ├── reset_data.py             # Wipe and reinitialize all databases (dev only)
│   └── migrate_db.py             # Alembic-based schema migration runner
│
├── services/                     # Business logic layer (orchestrates modules)
│   ├── auth_service.py           # Login, logout, token refresh, password change
│   ├── ingestion_service.py      # Coordinates ingestion pipeline, DB record creation
│   ├── query_service.py          # Custom Q&A lookup → vector retrieval → LLM generation
│   ├── stt_service.py            # Speech-to-text engine wrapper (Vosk/Moonshine)
│   └── admin_service.py          # User/department/role management business logic
│
├── .gitignore
├── .gitattributes
├── requirements.txt              # Full pinned dependency list (152 packages)
├── req.txt                       # Minimal/core dependency list
└── README.md
```

---

## 🔍 Module Deep Dive

### `/api` — FastAPI Application Layer

The API layer is the entry point for all client interactions. It is structured around **FastAPI routers**, each responsible for a specific domain:

- **`auth.py`**: Handles `POST /auth/login` (issues JWT access + refresh tokens), `POST /auth/logout` (blacklists the token in Redis), and `POST /auth/refresh` (issues a new access token from a valid refresh token).
- **`query.py`**: The core `POST /query` endpoint. Accepts a text or base64 audio payload, invokes the `QueryService`, and returns a structured response containing the answer, confidence, and a list of source documents with page references.
- **`ingestion.py`**: `POST /documents/upload` accepts multipart file uploads. The `RoleChecker` dependency ensures only users with upload permissions can call this endpoint.
- **`admin.py`**: Protected CRUD endpoints for managing users, roles, and departments. Managers can only modify users within their own department.
- **`qa.py`**: Admin-only endpoints to create, update, and delete custom Q&A pairs.

**Dependencies (`dependencies.py`)** provide injectable instances of the database session, Redis client, and the authenticated current user — keeping route handlers thin and testable.

**Middleware** is registered in `main.py` and handles:
- CORS configuration (restricted to the frontend's origin in production)
- Structured request logging (method, path, status code, duration)
- IP whitelist enforcement (configurable subnet allowlist)
- Global exception handling (maps `NexusAuthError` → 401, `NexusPermissionError` → 403, etc.)

---

### `/ingestion` — Document Processing Pipeline

The ingestion pipeline is a sequential processor that takes a raw file and produces a set of embedded, metadata-tagged vectors in Qdrant.

**Extractors (`extractors/`):**

Each extractor implements a common interface (`base_extractor.py`) with a `extract(file_path) -> List[PageContent]` method, where `PageContent` contains the text and its page or sheet number.

| Extractor | Libraries Used | Special Handling |
|---|---|---|
| `pdf_extractor.py` | `pdfplumber`, `pdfminer.six` | Falls back to `pytesseract` OCR for image-only pages; uses Google Cloud Vision API as a secondary fallback for high-accuracy OCR |
| `docx_extractor.py` | `python-docx` | Extracts body text, headers, footers, and table cell content |
| `xlsx_extractor.py` | `openpyxl`, `xlrd` | Iterates sheets and serializes cell values with their sheet name as context |
| `pptx_extractor.py` | `python-pptx` | Extracts text from text frames, notes slides, and table shapes |

**Chunker (`chunker.py`):**

Uses a sliding-window approach with configurable `chunk_size` (tokens) and `overlap` (tokens). Overlap ensures that sentences or concepts spanning chunk boundaries are captured in at least one chunk, preserving retrieval quality. The chunker is aware of sentence boundaries (using `spacy` tokenization) to avoid cutting mid-sentence.

**Embedder (`embedder.py`):**

Wraps `SentenceTransformer` with a lazy-loading singleton pattern to avoid reloading the model on every request. Default model: `all-MiniLM-L6-v2` (fast, 384-dimensional). The model path is configurable via environment variables, allowing drop-in replacement with larger models (e.g., `all-mpnet-base-v2`, `bge-large-en-v1.5`).

---

### `/retrieval` — Vector Search Engine

**`vector_store.py`:**
Wraps the Qdrant client with collection management helpers. On first startup, it creates the required Qdrant collection with the correct vector dimensionality and HNSW indexing parameters. Each point (vector) stored in Qdrant has a rich **payload** (metadata):

```json
{
  "text": "The original chunk text...",
  "source_file": "HR_Policy_2024.pdf",
  "page_number": 7,
  "department": "human_resources",
  "allowed_roles": ["admin", "manager", "employee"],
  "sensitivity": "internal",
  "ingested_at": "2024-11-15T10:30:00Z"
}
```

**`query_engine.py`:**
The `QueryEngine` is responsible for:
1. **Embedding** the user's query text using the same `embedder.py` singleton (ensures query and document vectors are in the same embedding space).
2. **Building RBAC filters**: Constructs a Qdrant `Filter` object that requires `department` to match the user's department AND `allowed_roles` to contain at least one of the user's roles. This is enforced at the database level — the LLM never receives context the user isn't authorized to see.
3. **Executing ANN search**: Calls `qdrant_client.search()` with the query vector and RBAC filter, returning the top-K most similar chunks.
4. **Re-ranking**: Applies a lightweight cross-encoder re-ranking step (using `scikit-learn` or a local cross-encoder model) to improve relevance ordering before passing to the LLM.
5. **Formatting context**: Assembles the retrieved chunks into a numbered, cited context block for the prompt builder.

---

### `/llm` — Language Model Orchestration

**`prompt_builder.py`:**
Constructs the final prompt sent to the LLM. The system prompt explicitly instructs the model to:
- Answer *only* using the provided context.
- Explicitly cite the source document and page number for every claim.
- Respond with "I don't have information on this topic in the authorized documents" if the context is insufficient.
- Never speculate or hallucinate facts.

The user query and retrieved context chunks (with source labels) are formatted into the `user` message. The structure follows the standard `[{role: "system", content: ...}, {role: "user", content: ...}]` chat format compatible with both Ollama and OpenAI-compatible APIs.

**`ollama_client.py`:**
Communicates with the locally running Ollama server via HTTP (`localhost:11434`). Supports both streaming and non-streaming response modes. The model name (e.g., `llama3`, `mistral`, `gemma2`) is configured via environment variable, making it trivial to switch models without code changes.

**`airllm_client.py`:**
Provides an alternative inference backend using AirLLM, which is optimized for running large models on consumer-grade GPU hardware through layer-by-layer loading and quantization. This is the recommended option for deployments without dedicated GPU servers.

---

### `/services` — Business Logic

Services orchestrate the lower-level modules into coherent business operations:

- **`auth_service.py`**: Validates credentials against bcrypt-hashed passwords in SQLite, issues JWT tokens, handles refresh token rotation, and invokes Redis to blacklist revoked tokens.
- **`query_service.py`**: First checks the custom Q&A repository for an exact or fuzzy match (using `RapidFuzz`). On a match, returns the canonical answer directly, bypassing the LLM. On a miss, invokes the `QueryEngine` and `PromptBuilder` → LLM pipeline.
- **`ingestion_service.py`**: Coordinates file saving, extraction, chunking, embedding, Qdrant upsert, and SQLite document record creation in a single transactional flow. Handles cleanup on partial failure.
- **`stt_service.py`**: Accepts a raw audio buffer, passes it to the configured local STT engine, and returns the transcribed text string to the query endpoint.
- **`admin_service.py`**: Enforces department-scoped access rules for manager-level operations (e.g., a manager cannot modify users outside their department even via direct API calls).

---

### `/core` — Configuration & Security

**`config.py`** uses `pydantic-settings` to load all configuration from environment variables (`.env` file). Key settings include:
- `QDRANT_HOST`, `QDRANT_PORT`, `QDRANT_COLLECTION_NAME`
- `REDIS_URL`
- `LLM_PROVIDER` (`ollama` or `airllm`), `LLM_MODEL_NAME`
- `EMBEDDING_MODEL_NAME`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `ALLOWED_IPS` (comma-separated CIDR ranges for IP whitelisting)
- `LOG_LEVEL`

**`security.py`** provides:
- `create_access_token()` / `create_refresh_token()` — JWT generation with configurable expiry.
- `get_current_user()` — FastAPI dependency that decodes and validates JWT, checks the token against Redis blacklist, and returns the authenticated user object.
- `RoleChecker` — A configurable dependency factory: `RoleChecker(["admin", "manager"])` generates a FastAPI dependency that raises a 403 if the current user's role is not in the allowed list.

---

### `/db` — Database Layer

Nexus uses the **Repository Pattern** to cleanly separate data access from business logic. Each repository class wraps a set of SQLAlchemy queries for a specific model.

**Models:**
- `User`: Stores username, bcrypt-hashed password, role, department assignment, and active/inactive status.
- `Department`: Stores department name and hierarchy level.
- `DocumentRecord`: Stores document metadata (filename, upload timestamp, uploader, allowed roles, department) — the actual document content lives in Qdrant.
- `CustomQA`: Stores question-answer pairs with priority scores and optional keyword triggers.
- `AuditLog`: Append-only table recording event type, user ID, document ID (if applicable), timestamp, and IP address.

Database schema migrations are managed via **Alembic**, invoked through `scripts/migrate_db.py`.

---

## 🔄 Data Flow

### Query Flow (Text)

```
User types question
       │
       ▼
React ChatPage → POST /query {text, jwt}
       │
       ▼
FastAPI auth middleware validates JWT
       │
       ▼
RoleChecker verifies role has query permission
       │
       ▼
QueryService.answer(question, user)
       ├─── Check Custom Q&A (RapidFuzz fuzzy match) ──► Match? Return canonical answer
       │
       └─── No match → QueryEngine.search(question, user)
                              │
                              ├── Embed question (SentenceTransformer)
                              ├── Build RBAC filter (role + department)
                              ├── Qdrant ANN search (top-K chunks)
                              └── Re-rank chunks
                                        │
                                        ▼
                              PromptBuilder.build(question, chunks)
                                        │
                                        ▼
                              LLMClient.generate(prompt)
                                        │
                                        ▼
                              Return answer + source citations
                                        │
                              Cache in Redis (TTL configurable)
                              Log to AuditLog
                                        │
                                        ▼
                              React displays answer with sources
```

### Ingestion Flow

```
Admin uploads file via DocumentsPage
       │
       ▼
POST /documents/upload (multipart: file, metadata JSON)
       │
       ▼
IngestionService.ingest(file, metadata, uploader)
       │
       ├── Save file to /uploads/ temp directory
       ├── Route to correct Extractor by MIME type
       │       └── Extract List[PageContent]
       ├── Chunker.chunk(pages) → List[Chunk]
       ├── Embedder.embed(chunks) → List[Vector]
       ├── VectorStore.upsert(vectors, payloads)  → Qdrant
       ├── DocumentRepo.create(metadata)           → SQLite
       └── AuditRepo.log("document_uploaded", ...)
```

---

## 🚀 Installation & Setup

### Prerequisites

Ensure the following are installed and running before starting Nexus:

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| Qdrant | Latest | Run via Docker (recommended) |
| Redis | 6+ | Run via Docker (recommended) |
| Ollama | Latest | With at least one model pulled |
| Tesseract OCR | 4.1+ | Required for OCR fallback in PDF extraction |
| Docker (optional) | Latest | Recommended for Qdrant + Redis |

### 1. Start Infrastructure Services

```bash
# Start Qdrant
docker run -d -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage:z \
  qdrant/qdrant

# Start Redis
docker run -d -p 6379:6379 redis:latest

# Start Ollama (if using local LLM)
ollama serve
# Pull a model (e.g., Llama 3)
ollama pull llama3
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
source venv/bin/activate       # Linux/macOS
# venv\Scripts\activate        # Windows

# Install all dependencies
pip install -r requirements.txt

# Install Tesseract system dependency (Ubuntu/Debian)
sudo apt-get install tesseract-ocr

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your configuration (see Configuration section below)

# Initialize the relational database (creates SQLite file and schema)
python -m scripts.reset_data

# Create the first SuperAdmin user
python -m scripts.create_admin
# Follow the prompts to set username and password

# Start the FastAPI backend server
uvicorn api.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000` and the interactive Swagger docs at `http://localhost:8000/docs`.

### 4. Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install Node.js dependencies
npm install

# Start the Vite development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## ⚙️ Configuration

Nexus is configured entirely via environment variables. Copy `.env.example` to `.env` and set the following:

```env
# ─── Database ───────────────────────────────────────────────────
DATABASE_URL=sqlite:///./nexus.db

# ─── Qdrant Vector Database ─────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION_NAME=nexus_documents

# ─── Redis Cache ────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0
CACHE_TTL_SECONDS=3600

# ─── LLM Configuration ──────────────────────────────────────────
LLM_PROVIDER=ollama             # Options: ollama, airllm
LLM_MODEL_NAME=llama3           # Model name as known to Ollama
OLLAMA_BASE_URL=http://localhost:11434

# ─── Embedding Model ────────────────────────────────────────────
EMBEDDING_MODEL_NAME=all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# ─── JWT Security ───────────────────────────────────────────────
JWT_SECRET_KEY=your-256-bit-secret-key-here     # Use: openssl rand -hex 32
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# ─── Network Security ───────────────────────────────────────────
ALLOWED_IPS=                    # Leave empty to allow all; e.g., 10.0.0.0/8,192.168.1.0/24
CORS_ORIGINS=http://localhost:5173

# ─── Retrieval Settings ─────────────────────────────────────────
RETRIEVAL_TOP_K=10              # Number of chunks retrieved per query
RETRIEVAL_SCORE_THRESHOLD=0.65  # Minimum cosine similarity for a chunk to be included

# ─── Document Chunking ──────────────────────────────────────────
CHUNK_SIZE_TOKENS=512
CHUNK_OVERLAP_TOKENS=64

# ─── Logging ────────────────────────────────────────────────────
LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR
```

---

## 📡 API Reference

All endpoints require a valid JWT Bearer token in the `Authorization` header unless marked as public.

### Authentication

| Method | Endpoint | Description | Auth |
|---|---|---|---|
| `POST` | `/auth/login` | Authenticate user, receive access + refresh tokens | Public |
| `POST` | `/auth/logout` | Revoke current token (blacklist in Redis) | Required |
| `POST` | `/auth/refresh` | Exchange refresh token for new access token | Required |
| `PUT` | `/auth/password` | Change authenticated user's password | Required |

### Query

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/query` | Submit a question; returns answer + source citations | Employee+ |
| `POST` | `/query/voice` | Submit base64-encoded audio; transcribes then queries | Employee+ |
| `GET` | `/query/history` | Retrieve authenticated user's query history | Employee+ |

**`POST /query` Request Body:**
```json
{
  "question": "What is the company's remote work policy?",
  "stream": false
}
```

**`POST /query` Response:**
```json
{
  "answer": "Based on the HR Policy document, employees may work remotely up to 3 days per week with manager approval...",
  "sources": [
    {
      "file": "HR_Remote_Work_Policy_2024.pdf",
      "page": 3,
      "excerpt": "...employees are permitted to work remotely up to three days per week..."
    }
  ],
  "query_id": "q_a3f2b1",
  "from_cache": false,
  "from_custom_qa": false
}
```

### Document Management

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `POST` | `/documents/upload` | Upload and ingest a document | Employee+ |
| `GET` | `/documents` | List documents accessible to the current user | Employee+ |
| `GET` | `/documents/{id}` | Get document metadata | Employee+ |
| `DELETE` | `/documents/{id}` | Delete document and its vectors | Admin |

### Administration

| Method | Endpoint | Description | Required Role |
|---|---|---|---|
| `GET` | `/admin/users` | List all users (Admin) or department users (Manager) | Manager+ |
| `POST` | `/admin/users` | Create a new user | Admin |
| `PUT` | `/admin/users/{id}` | Update user role or department | Admin / Manager (dept only) |
| `DELETE` | `/admin/users/{id}` | Deactivate a user | Admin |
| `GET` | `/admin/departments` | List all departments | Admin, CEO |
| `POST` | `/admin/departments` | Create a department | Admin, CEO |
| `GET` | `/admin/audit-logs` | View audit logs | Admin, CEO, Manager (dept only) |
| `GET` | `/admin/qa` | List custom Q&A pairs | Admin |
| `POST` | `/admin/qa` | Create a custom Q&A pair | Admin |
| `PUT` | `/admin/qa/{id}` | Update a custom Q&A pair | Admin |
| `DELETE` | `/admin/qa/{id}` | Delete a custom Q&A pair | Admin |

Full interactive API documentation is available at `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc` (ReDoc).

---

## 🔒 Access Control Matrix

Nexus implements a hierarchical RBAC model. Access is cumulative — higher roles inherit all permissions of lower roles within their scope.

| Action | Admin | CEO | Manager | Employee |
|---|:---:|:---:|:---:|:---:|
| Ask Questions | ✅ | ✅ | ✅ | ✅ |
| Upload Documents | ✅ | ✅ | ✅ | ✅ |
| Delete Documents | ✅ | ❌ | ❌ | ❌ |
| View Own Query History | ✅ | ✅ | ✅ | ✅ |
| View All Query History | ✅ | ✅ | Dept. only | ❌ |
| View Audit Logs | ✅ | ✅ | Dept. only | Self only |
| Create Users | ✅ | ❌ | ❌ | ❌ |
| Edit Users | ✅ | ❌ | Dept. only | ❌ |
| Deactivate Users | ✅ | ❌ | ❌ | ❌ |
| Manage Custom Q&A | ✅ | ❌ | ❌ | ❌ |
| Manage Global Departments | ✅ | ✅ | ❌ | ❌ |
| View System Configuration | ✅ | ❌ | ❌ | ❌ |

> **"Dept. only"** means the Manager can perform the action, but only for users and documents within their own assigned department.

**Document-Level Access:** In addition to role-based restrictions, each document has an explicit `allowed_roles` list set at upload time. A Manager-role user will not see a document tagged `allowed_roles: ["admin", "ceo"]` even if they have general query access. This provides fine-grained, document-level isolation.

---

## 🛡️ Security & Compliance

### Authentication
- **JWT with RS256/HS256**: Short-lived access tokens (default: 60 minutes) and long-lived refresh tokens (default: 7 days).
- **Token Blacklisting**: On logout, the token's JTI (JWT ID) is stored in Redis with TTL matching the token's remaining validity. Subsequent requests with the same token are rejected.
- **Password Security**: All passwords are hashed with `bcrypt` (cost factor configurable). Plain-text passwords are never stored or logged.

### Network Security
- **IP Whitelisting**: The `ALLOWED_IPS` environment variable accepts CIDR notation ranges. Requests from IPs outside these ranges receive a 403 response before any authentication is attempted.
- **CORS**: Strict origin allowlist configured via `CORS_ORIGINS`. The wildcard `*` origin is disabled in production mode.
- **HTTPS**: In production, deploy behind a reverse proxy (nginx, Caddy) with TLS termination. The backend enforces `Strict-Transport-Security` headers when `FORCE_HTTPS=true`.

### Data Security
- **Zero-Trust Vector Retrieval**: RBAC filters are applied at the Qdrant query level. The Python application layer never receives unauthorized vectors — they are filtered out by the database engine before results are returned.
- **No External Data Transmission**: All LLM inference (Ollama/AirLLM), embedding (sentence-transformers), and speech-to-text (Vosk/Moonshine) run locally. No document content, queries, or responses are sent to external APIs.
- **Audit Logging**: All write operations (document uploads, deletions, user changes) and all queries (with user ID, timestamp, question hash) are logged asynchronously to an append-only SQLite table.

### Compliance Considerations
- The immutable audit log supports GDPR Article 30 (records of processing activities) and ISO 27001 access control requirements.
- Department-level document isolation supports need-to-know data classification policies.
- Complete offline operation meets data residency requirements for regulated industries.

---

---

## 🔧 Scripts & Utilities

| Script | Usage | Description |
|---|---|---|
| `scripts/create_admin.py` | `python -m scripts.create_admin` | Interactively creates the first SuperAdmin account. Required for initial setup. |
| `scripts/reset_data.py` | `python -m scripts.reset_data` | **⚠️ Destructive.** Drops and recreates all SQLite tables and deletes the Qdrant collection. For development only. |
| `scripts/migrate_db.py` | `python -m scripts.migrate_db` | Runs pending Alembic database migrations. Use this for production schema updates. |

---

## 🎨 Frontend Overview

The React frontend is a single-page application (SPA) with client-side routing via React Router Dom.

### Pages

- **Login Page (`/login`)**: Animated login form. On success, stores JWT in memory (access) and `httpOnly` cookie (refresh). Redirects to chat.
- **Chat Page (`/chat`)**: The core interface. A conversation panel displays the Q&A history with source citation chips that expand to show the document excerpt. A microphone button activates the STT service. Framer Motion provides message entrance animations.
- **Documents Page (`/documents`)**: Drag-and-drop file uploader with a progress indicator. Lists uploaded documents with their metadata, department tags, and allowed roles. Admins see a delete button on each document.
- **Admin Page (`/admin`)**: Tabbed dashboard with User Management (create, edit role/department, deactivate), Department Management (create/delete), Custom Q&A Management, and Audit Log Viewer (filterable by date, user, event type).

### State Management

Global authentication state (current user, role, JWT) is managed via `AuthContext` (React Context API). The Axios client instance (`api/client.js`) automatically attaches the JWT as a Bearer token to every request and handles 401 responses by attempting a token refresh before retrying the original request.

### Build

```bash
# Development
cd frontend && npm run dev

# Production build
cd frontend && npm run build
# Output in frontend/dist/ — serve with nginx or any static file server
```

---

## 🐳 Deployment

### Production Docker Compose (Example)

```yaml
version: '3.8'

services:
  nexus-api:
    build: .
    command: uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
    ports:
      - "8000:8000"
    environment:
      - QDRANT_HOST=qdrant
      - REDIS_URL=redis://redis:6379/0
      - LLM_PROVIDER=ollama
    volumes:
      - ./nexus.db:/app/nexus.db
      - ./uploads:/app/uploads
    depends_on:
      - qdrant
      - redis

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_storage:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  qdrant_storage:
  redis_data:
```

### Recommended Production Architecture

```
Internet → Firewall/VPN → nginx (TLS) → FastAPI (Uvicorn, 4 workers)
                                       ↓
                               Qdrant (internal)
                               Redis (internal)
                               Ollama (GPU server, internal)
```

For high-availability deployments, Qdrant supports distributed mode and replication. Redis can be deployed as a cluster. FastAPI workers can be scaled horizontally behind a load balancer.

---

## 🤝 Contributing

Contributions are welcome. Please follow these guidelines:

1. Fork the repository and create a feature branch (`git checkout -b feature/your-feature`).
2. Follow PEP 8 for Python code. Use `black` for formatting and `flake8` for linting.
3. Ensure new functionality is well-documented with clear docstrings and inline comments.
4. Update this README and any relevant docstrings for new features.
5. Open a Pull Request with a clear description of the change and its motivation.

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install black flake8

# Run linter
flake8 . --max-line-length=100 --exclude=venv,__pycache__

# Run formatter
black . --line-length=100
```

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 👤 Author

**hackerxhari** — [github.com/hackerxhari](https://github.com/hackerxhari)

---

<p align="center">
  Built with ❤️ for enterprises that take data privacy seriously.
</p>
