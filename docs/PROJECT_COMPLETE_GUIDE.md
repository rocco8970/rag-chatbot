# RAG Chatbot — Complete Project Guide

> **Project:** RAG-Based Intelligent Document Q&A System  
> **University:** Jamia Hamdard, Department of Computer Science  
> **Academic Year:** 2024–25  
> **Last Updated:** 2026-05-18

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Project File Map](#2-project-file-map)
3. [How It Works — Step by Step](#3-how-it-works--step-by-step)
4. [All Code Files Explained](#4-all-code-files-explained)
5. [System Requirements](#5-system-requirements)
6. [Setup Instructions](#6-setup-instructions)
7. [Running the App](#7-running-the-app)
8. [Environment Variables Reference](#8-environment-variables-reference)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. What This Project Does

This is a **RAG (Retrieval-Augmented Generation) Chatbot** — a web application that:

1. Lets you **upload documents** (PDF, DOCX, TXT, MD, CSV)
2. **Splits and embeds** those documents as vectors in ChromaDB (a local vector database)
3. When you **ask a question**, it finds the most relevant document chunks using cosine similarity
4. **Passes those chunks to a free AI model** (Google Gemini or Groq/Llama) to generate a grounded answer
5. Shows the answer with **source attribution** — which document and which chunk the answer came from

Two front-end options are available:
- **Option A:** Original Streamlit UI (single Python file, simple)
- **Option B:** React 18 + FastAPI UI (modern, with word-by-word streaming)

Both options use the **same core RAG pipeline** in `src/`.

---

## 2. Project File Map

```
rag-chatbot/
│
├── streamlit_app.py              ← Option A: Original Streamlit web UI
│
├── backend/
│   └── main.py                   ← Option B: FastAPI backend (REST + WebSocket)
│
├── frontend/                     ← Option B: React 18 frontend
│   └── src/
│       ├── App.jsx               ← Root layout
│       └── components/
│           ├── Sidebar.jsx       ← Upload, model select, document list
│           ├── ChatWindow.jsx    ← Chat + streaming WebSocket
│           └── Message.jsx       ← Message bubbles + markdown + sources
│
├── src/                          ← Core RAG pipeline (shared by both UIs)
│   ├── document_utils.py         ← Text extraction + chunking
│   ├── embeddings_utils.py       ← Sentence Transformers embeddings
│   ├── response_generation.py    ← Gemini + Groq LLM calls + streaming
│   ├── rag_pipeline.py           ← Orchestrates all pipeline steps
│   └── evaluation.py             ← Retrieval evaluation metrics
│
├── scripts/
│   ├── setup_database.py         ← (Legacy) PostgreSQL setup — not used
│   └── checking_db.py            ← ChromaDB connection check
│
├── tests/
│   ├── test_app.py               ← Application tests
│   └── test_database.py          ← Database tests
│
├── docs/
│   ├── TECHNICAL_ARCHITECTURE.md ← Deep technical documentation
│   ├── USER_GUIDE.md             ← End-user guide
│   ├── DEPLOYMENT.md             ← Deployment instructions
│   ├── PROJECT_COMPLETE_GUIDE.md ← This file
│   └── PROJECT_REPORT.md         ← Supervisor/academic explanation
│
├── chroma_db/                    ← Local vector database (auto-created)
├── data/uploads/                 ← Temp folder for uploads
├── requirements.txt              ← Python dependencies
├── .env                          ← Your secrets (never commit this)
├── .env.example                  ← Template for .env
└── README.md
```

---

## 3. How It Works — Step by Step

### A. Document Upload Flow

```
User uploads PDF / DOCX / TXT / MD / CSV
        ↓
Text extracted using format-specific parser:
  - PDF  → PyMuPDF (fitz)
  - DOCX → python-docx
  - CSV  → pandas
  - TXT / MD → built-in file read
        ↓
Text split into chunks:
  - Chunk size: 500 characters
  - Overlap: 50 characters (so context at boundaries is not lost)
        ↓
Each chunk encoded into a 384-dimensional vector
  using Sentence Transformers (all-MiniLM-L6-v2)
  — runs LOCALLY on your machine, no API needed
        ↓
Chunks + vectors + metadata saved to ChromaDB
  stored in ./chroma_db/ on disk (persistent)
```

### B. Query / Chat Flow

```
User types: "What does the document say about [topic]?"
        ↓
Question encoded into 384-dim vector
  (same Sentence Transformers model)
        ↓
ChromaDB cosine similarity search:
  finds top-K chunks closest to the question vector
  (default K = 5)
        ↓
Retrieved chunks joined as context string
        ↓
Prompt built:
  "Answer ONLY from the context below:
   [context chunks]
   Question: [user question]"
        ↓
Prompt sent to free LLM API:
  → Gemini: google.genai.Client → generate_content()
  → Groq:   groq.Groq → chat.completions.create()
        ↓
Answer returned to user with source metadata
  (filename + chunk number for each source)
```

### C. Streaming (React UI)

```
User sends question via WebSocket connection
        ↓
FastAPI backend retrieves context (same as above)
        ↓
LLM API called in streaming mode:
  → Gemini: generate_content_stream()
  → Groq:   completions.create(stream=True)
        ↓
Each token (word/part) sent to browser via WebSocket
  as JSON: {"token": "word", "done": false}
        ↓
React appends each token to the displayed message
  (user sees answer appearing word by word)
        ↓
Final WebSocket message: {"done": true, "sources": [...]}
```

---

## 4. All Code Files Explained

### `src/document_utils.py`

Handles reading and chunking documents.

**Classes:**

`DocumentProcessor`
- `process_file(path)` — detects format, calls correct parser, returns `(text, metadata)`

`TextChunker`
- `chunk_text(text)` — splits long text into overlapping windows of 500 characters

**Why overlap?** When a sentence falls at the boundary of two chunks, the 50-char overlap ensures it appears fully in at least one chunk. This prevents losing context at chunk edges.

---

### `src/embeddings_utils.py`

Generates vector representations of text.

**Class: `EmbeddingsManager`**
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Output: 384-dimensional float vectors
- Runs on CPU locally — no API key, no cost, no internet
- `get_embeddings(texts)` — batch encode list of strings
- `get_query_embedding(query)` — encode a single query string

**Why Sentence Transformers?** They are free, run locally, and produce semantically meaningful vectors where similar texts produce similar vectors. The model is small (~80MB) but effective for document retrieval.

---

### `src/response_generation.py`

Handles all communication with LLM APIs.

**Class: `ResponseGenerator`**

| Method | Purpose |
|--------|---------|
| `_init_gemini()` | Initialise Google Gemini client |
| `_init_groq()` | Initialise Groq client |
| `generate_response(question, context)` | Standard call — waits for full response |
| `stream_response(question, context)` | Generator — yields tokens one by one |
| `_stream_gemini(prompt)` | Gemini streaming with model fallback chain |
| `_stream_groq(prompt)` | Groq streaming |
| `_build_prompt(question, context)` | Builds the instruction prompt |

**Gemini model fallback:** Tries `gemini-2.5-flash` first, then falls back to `gemini-2.0-flash`, etc. This ensures the app keeps working even if a specific model becomes unavailable on the free tier.

---

### `src/rag_pipeline.py`

Orchestrates the full pipeline end-to-end.

**Class: `RAGPipeline`**

| Method | What it does |
|--------|-------------|
| `__init__(llm_provider)` | Initialises all components, connects to ChromaDB |
| `ingest_document(file_path)` | Extract → chunk → embed → store |
| `query(question, top_k)` | Embed query → search → build context → generate response |
| `get_stats()` | Return chunk count + query history |
| `clear_all()` | Delete ChromaDB collection |

---

### `src/evaluation.py`

Measures retrieval quality for academic evaluation.

**Class: `RAGEvaluator`**
- `evaluate_retrieval(query, expected_keywords)` — checks how many expected keywords appear in retrieved chunks. Returns a recall score (0 to 1).
- `run_test_suite(test_cases)` — runs multiple test cases and saves results to `evaluation/eval_results.json`

---

### `streamlit_app.py`

The original single-file Streamlit web application. Contains all UI and pipeline logic in one file, using `st.session_state` to persist objects across page interactions.

Key session state objects:
- `embeddings_manager` — loaded once, reused for all queries
- `response_generators` — one per provider, cached to avoid re-initialising API clients
- `collection` — ChromaDB collection handle
- `documents` — list of uploaded document metadata
- `messages` — chat history

---

### `backend/main.py`

FastAPI backend exposing the RAG pipeline via REST endpoints and WebSocket.

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/stats` | Return `{doc_count, chunk_count}` |
| `GET` | `/api/documents` | List all ingested documents |
| `POST` | `/api/upload` | Upload + process a document file |
| `DELETE` | `/api/documents` | Clear all documents |
| `WebSocket` | `/ws/chat` | Streaming chat |

The `RAGPipeline` is initialised once at application startup and shared across all requests via `app.state.pipeline`.

---

## 5. System Requirements

| Component | Minimum | Notes |
|-----------|---------|-------|
| Python | 3.9+ | 3.11 recommended |
| RAM | 4 GB | 8 GB for large documents |
| Disk | 500 MB | For model cache + ChromaDB |
| Internet | Yes | For Gemini/Groq API calls only |
| Node.js | 18+ | React UI only |

No GPU required. No database server required. No paid API keys required.

---

## 6. Setup Instructions

### Step 1 — Install Python packages

```bash
pip install -r requirements.txt
```

### Step 2 — Create `.env` file

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Edit `.env`:
```env
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here
LLM_PROVIDER=gemini
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=5
```

### Step 3 — (React UI only) Install frontend packages

```bash
cd frontend
npm install
```

---

## 7. Running the App

### Streamlit UI

```bash
streamlit run streamlit_app.py
# → http://localhost:8501
```

### React + FastAPI UI

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
# → http://localhost:5173
```

---

## 8. Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | — | Google Gemini API key (free tier) |
| `GROQ_API_KEY` | — | Groq API key (free tier) |
| `LLM_PROVIDER` | `gemini` | Default LLM: `gemini` or `groq` |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap characters between chunks |
| `TOP_K` | `5` | Default chunks to retrieve per query |

---

## 9. Troubleshooting

| Problem | Solution |
|---------|---------|
| `GEMINI_API_KEY not found` | Check `.env` exists in project root with correct key |
| `All Gemini models failed` | Try switching to Groq; check internet connection |
| First startup very slow | Normal — embedding model downloads once (~80MB) |
| React UI shows blank page | Make sure FastAPI backend is running on port 8000 |
| `No documents` in chat | Upload at least one file via the sidebar first |
| ChromaDB error | Delete `chroma_db/` folder and restart |
| PDF fails to upload | Ensure PDF is text-based, not a scanned image |
