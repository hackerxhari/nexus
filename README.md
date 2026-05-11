# Nexus: Internal AI Knowledge Base

Nexus is a highly secure, enterprise-grade, internal AI Knowledge Base system. It allows organizations to securely ingest, process, and query massive volumes of internal documents (PDFs, Office Documents, Spreadsheets, Images, etc.) using Retrieval-Augmented Generation (RAG). 

By integrating strict Role-Based Access Control (RBAC), offline Large Language Models (LLMs), and localized speech-to-text engines, Nexus ensures that highly sensitive corporate data never leaves the internal network.

---

## 🌟 Key Features

- **Retrieval-Augmented Generation (RAG)**: Employs state-of-the-art sentence transformers to embed document chunks into a highly scalable Qdrant Vector Database.
- **Enterprise RBAC**: Multi-tiered access control enforcing hierarchy and department-level isolation. An employee only gets answers based on documents their role and department explicitly authorize them to view.
- **Dynamic Multi-Modal Ingestion**: Automatically processes PDFs (with OCR fallback for scanned images), Word Docs, Excel Spreadsheets, PowerPoints, and plain text.
- **Custom Question & Answers**: Organizations can inject high-priority, canonical answers directly into the system, bypassing the LLM generation for absolute accuracy on critical queries.
- **Speech-to-Text Integration**: Native integration with local STT engines allowing users to verbally query the system.
- **Offline / Edge Ready**: Can run entirely offline using local instances of Ollama for LLM inference and Vosk/Moonshine for Speech-to-Text. No cloud dependencies required.
- **Stunning UI**: A sleek, modern React frontend leveraging Framer Motion for buttery-smooth animations, dark mode aesthetics, and an intuitive administrative dashboard.

---

## 🏗️ Architecture Overview

The system is cleanly decoupled into a robust FastAPI backend and a responsive React frontend.

### 1. The Ingestion Pipeline (`/ingestion`)
Documents uploaded via the UI pass through an extraction layer (`extractors/`) tailored to the file type. The text is intelligently chunked (`chunker.py`) utilizing semantic overlap to retain context. Chunks are embedded using `SentenceTransformers` (`embedder.py`) and stored in **Qdrant** with rigorous metadata (hierarchy, department, allowed roles) attached to each vector.

### 2. The Retrieval Engine (`/retrieval`)
When a query is made, the `QueryEngine` embeds the user's question, applies hard database filters matching the user's explicit roles/departments, and executes an Approximate Nearest Neighbor (ANN) search against Qdrant. Context chunks are re-ranked and formatted.

### 3. LLM Orchestration (`/llm`)
The `PromptBuilder` merges the retrieved context with the user's query and injects a strong system prompt forbidding hallucination. The payload is sent to the configured LLM provider (`ollama_client.py` or `airllm_client.py`) to generate a conversational response with explicit source citations.

### 4. Admin & Security (`/api`, `/core`)
FastAPI routes are aggressively protected by `RoleChecker` logic (`core/security.py`). JWT-based authentication enforces role hierarchies. All queries and document interactions are logged asynchronously for compliance (`db/repositories/audit_repo.py`).

---

## 🛠️ Technology Stack

### Backend
- **Python 3.10+**: Core backend runtime.
- **FastAPI**: High-performance asynchronous web framework.
- **SQLAlchemy & SQLite**: Relational database for user management, departments, and audit logs.
- **Qdrant**: Vector database optimized for RAG.
- **Redis**: Low-latency caching layer for LLM responses and rate limiting.
- **Sentence-Transformers**: Open-source embedding models (e.g., `all-MiniLM-L6-v2`).
- **Ollama / AirLLM**: Localized LLM inference engines.

### Frontend
- **React 18 + Vite**: Lightning-fast UI development environment.
- **Framer Motion**: Premium layout animations and page transitions.
- **React Router Dom**: Client-side routing.

---

## 🚀 Installation & Setup

### Prerequisites
1. **Python 3.10+**
2. **Node.js 18+**
3. **Qdrant Container/Instance** (Running on port 6333)
4. **Redis Server** (Running on port 6379)
5. **Ollama** (Running locally with a model pulled, e.g., `ollama run llama3`)

### Backend Setup
```bash
# 1. Clone and navigate to the root directory
cd nexus

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up the environment variables
cp .env.example .env
# Edit .env and ensure QDRANT_HOST, REDIS_URL, and LLM_PROVIDER are configured

# 5. Initialize the database and create the SuperAdmin
python -m scripts.reset_data
python -m scripts.create_admin

# 6. Run the FastAPI server
uvicorn api.main:app --reload --port 8000
```

### Frontend Setup
```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install NPM dependencies
npm install

# 3. Start the development server
npm run dev
```

---

## 📁 Directory Structure

```text
nexus/
├── api/                # FastAPI Routers, Schemas, Dependencies, Middleware
├── cache/              # Redis caching configurations and services
├── core/               # App configuration, Security Utils, Custom Exceptions
├── db/                 # SQLAlchemy Models, Base Setup, and Repositories
├── frontend/           # React Frontend Application (Pages, Components, Context)
├── ingestion/          # Document Parsers (PDF, Docx), Chunker, Embedder Pipeline
├── llm/                # LLM Clients (Ollama, Base) and Prompt Builder
├── retrieval/          # Qdrant Vector Store wrapper and Query Engine
├── scripts/            # Admin creation, DB Reset, DB Migration tools
├── services/           # Core Business Logic (Auth, Ingestion, Q&A, STT)
└── uploads/            # Temporary storage for ingested documents
```

---

## 🔒 Security & Compliance
- **Zero-Trust Defaults**: By default, documents are inaccessible unless a user's role explicitly intersects with the document's allowed roles.
- **Network Isolation**: IP Whitelisting capabilities restrict backend API access to defined corporate subnets.
- **Audit Trails**: Every question asked, and every document uploaded or deleted, is permanently logged to the SQLite relational database.
- **Token Blacklisting**: JWT tokens are revoked entirely upon logout or role deactivation using Redis.

## 👥 Access Control Matrix

| Action                  | Admin | CEO | Manager | Employee |
|-------------------------|:-----:|:---:|:-------:|:--------:|
| Ask Questions           |   ✓   |  ✓  |    ✓    |    ✓     |
| Upload Documents        |   ✓   |  ✓  |    ✓    |    ✓     |
| View Audit Logs         |   ✓   |  ✓  | Dept.   | Self     |
| Manage Users            |   ✓   |  x  | Dept.   |    x     |
| Manage Custom Q&A       |   ✓   |  x  |    x    |    x     |
| Manage Global Depts     |   ✓   |  ✓  |    x    |    x     |

*(Note: "Dept." indicates the manager can perform these actions strictly for users within their own department).*
