# RAG Chatbot — Complete Project Guide

> **Author:** Ali Khan | **Email:** ali.khan@kimbal.io  
> **Last Updated:** 2026-04-30  
> **Status:** Production-ready after all bug fixes applied

---

## Table of Contents

1. [What This Project Does](#1-what-this-project-does)
2. [Project File Map](#2-project-file-map)
3. [How It Works — Step by Step](#3-how-it-works--step-by-step)
4. [System Requirements](#4-system-requirements)
5. [Setup Instructions (Full)](#5-setup-instructions-full)
6. [Running the App](#6-running-the-app)
7. [Using the App](#7-using-the-app)
8. [All Code Files Explained](#8-all-code-files-explained)
9. [Database Schema](#9-database-schema)
10. [Bugs Fixed](#10-bugs-fixed)
11. [Environment Variables Reference](#11-environment-variables-reference)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What This Project Does

This is a **RAG (Retrieval-Augmented Generation) Chatbot** — a web application that:

1. Lets you **upload company documents** (PDF, Word, TXT)
2. **Splits and embeds** those documents as vectors in a database
3. When you ask a **question**, it finds the most relevant document chunks
4. **Passes them to an AI model** (OpenAI GPT or AWS Bedrock Claude) to answer
5. Shows you **3 answers side-by-side**:
   - Without context (pure AI knowledge)
   - With context (uses your uploaded documents)
   - With guardrail (strictly uses only your documents — no hallucination)

**Real-world use case:** Upload your company's product manuals, specifications, or SOPs and ask questions like "What are the features of AMI Smart Meter?" — and get accurate answers grounded in your own documents.

---

## 2. Project File Map

```
Desktop/ai/
├── ali.py                          ← Simple Python exception practice (not part of app)
├── exceptions.py                   ← Python exception examples (not part of app)
│
└── rag-chatbot/
    ├── streamlit_app.py            ← MAIN APP — Streamlit web UI (run this)
    ├── document_utils.py           ← PDF/DOCX/TXT text extraction + chunking
    ├── embeddings_utils.py         ← OpenAI embedding generation
    ├── response_generation.py      ← LLM response generation (OpenAI + Bedrock)
    │
    ├── scripts/
    │   └── setup_database.py       ← ONE-TIME: Creates PostgreSQL tables
    │
    ├── tests/
    │   ├── test_app.py             ← App tests (pytest)
    │   └── test_database.py        ← Database tests (pytest)
    │
    ├── knowledge/                  ← Put sample documents here (currently empty)
    │
    ├── requirements.txt            ← Python packages to install
    ├── .env.example                ← Template for your secrets
    ├── .env                        ← YOUR secrets (create this, never commit)
    │
    ├── README.md                   ← Short readme
    ├── TECHNICAL_ARCHITECTURE.md   ← Deep technical docs
    ├── DEPLOYMENT.md               ← Deployment guide
    ├── USER_GUIDE.md               ← End-user guide
    └── PROJECT_COMPLETE_GUIDE.md   ← This file
```

---

## 3. How It Works — Step by Step

### A. Document Upload Flow

```
You upload a PDF/DOCX/TXT file
        ↓
Text is extracted (pdfplumber / python-docx)
        ↓
Text is cleaned (remove extra spaces, normalize newlines)
        ↓
Text is split into ~1000-character chunks with 200-char overlap
(overlap keeps context at boundaries)
        ↓
Each chunk gets prefixed: "Product: filename\n\n[chunk text]"
        ↓
OpenAI generates a 1536-dimension vector for each chunk
(in batches of 128 for speed)
        ↓
Document metadata + all chunks + their vectors → saved to PostgreSQL
```

### B. Chat / Query Flow

```
You type: "What voltage does AMI meter support?"
        ↓
OpenAI generates a vector for your question
        ↓
PostgreSQL uses pgvector <-> operator to find nearest chunk vectors
(HNSW index makes this fast even with thousands of chunks)
        ↓
Top-K most similar chunks retrieved, filtered by min_similarity
        ↓
3 parallel LLM calls:
  [Col 1] Question only → "Without Context" answer
  [Col 2] Question + chunks → "With Context" answer
  [Col 3] Question + chunks + strict rules → "Guardrail" answer
        ↓
All 3 answers shown side-by-side with timing info
```

### C. Enhanced Embeddings (Optional)

```
For better specific-attribute searches:
        ↓
GPT-4o-mini reads each chunk and extracts structured JSON:
  {"product_name": "AMI Meter", "voltage": "240V", "features": [...]}
        ↓
That JSON gets embedded (instead of raw text)
        ↓
Stored as embedding_type='enhanced' (original stays as 'general')
        ↓
You can switch between general/enhanced in the sidebar
```

---

## 4. System Requirements

### Required
| Component | Version | Status |
|-----------|---------|--------|
| Python | 3.9+ | ✅ 3.11.9 installed |
| PostgreSQL | 12+ | ❌ Must install |
| pgvector extension | 0.4+ | ❌ Install after PostgreSQL |
| OpenAI API Key | — | ❌ Must obtain |

### Optional (for AWS Bedrock models)
| Component | Version |
|-----------|---------|
| AWS Account with Bedrock access | — |
| AWS Access Key + Secret | — |
| Bedrock model access enabled | — |

### Python Packages (auto-installed via requirements.txt)
| Package | Purpose |
|---------|---------|
| streamlit 1.x | Web UI framework |
| openai 1.x | Embeddings + GPT chat |
| boto3 | AWS Bedrock calls |
| psycopg2-binary | PostgreSQL driver |
| pdfplumber | PDF text extraction |
| python-docx | DOCX text extraction |
| python-dotenv | Load .env file |
| pgvector | Vector type helpers |
| pytest + pytest-cov | Testing |

---

## 5. Setup Instructions (Full)

### Step 1: Install PostgreSQL

Download from: https://www.postgresql.org/download/windows/

- Use the installer wizard
- Default port: **5432**
- Set a password for `postgres` user
- **Important:** Check the box to include Stack Builder after install

### Step 2: Install pgvector Extension

Option A — Via Stack Builder (easiest):
1. Open Stack Builder (comes with PostgreSQL)
2. Go to: Database Extensions → pgvector
3. Install it

Option B — Manual:
1. Download from https://github.com/pgvector/pgvector/releases
2. Follow the Windows instructions in their README

Option C — Via psql command (after PostgreSQL is running):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 3: Create Database and User

Open **pgAdmin** (installed with PostgreSQL) or **psql**, then run:

```sql
-- Create the database user
CREATE USER admin WITH PASSWORD 'your_secure_password';

-- Create the database
CREATE DATABASE admin OWNER admin;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE admin TO admin;
```

### Step 4: Copy .env.example → .env

```
cd "C:\Users\MDAliKhan\OneDrive - Sinhal Udyog pvt ltd\Desktop\ai\rag-chatbot"
copy .env.example .env
```

Then open `.env` in Notepad and fill in:

```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxx    ← Get from platform.openai.com
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=admin
DB_USER=admin
DB_PASSWORD=your_secure_password              ← What you set in Step 3
```

### Step 5: Install Python Packages

```bash
cd "C:\Users\MDAliKhan\OneDrive - Sinhal Udyog pvt ltd\Desktop\ai\rag-chatbot"
pip install -r requirements.txt
```

### Step 6: Create Database Tables (one-time)

```bash
cd "C:\Users\MDAliKhan\OneDrive - Sinhal Udyog pvt ltd\Desktop\ai\rag-chatbot"
python scripts/setup_database.py
```

Expected output:
```
Loading configuration from environment...
Connecting to database...
Creating pgvector extension if not exists...
Creating table: company_documents
Creating table: document_chunks
Creating table: conversations
Creating HNSW index on document_chunks.embedding (vector)
Creating B-tree indexes...
Granting privileges to user 'admin'...
All expected tables exist: ['company_documents', 'conversations', 'document_chunks']
Database schema setup completed successfully.
```

---

## 6. Running the App

```bash
cd "C:\Users\MDAliKhan\OneDrive - Sinhal Udyog pvt ltd\Desktop\ai\rag-chatbot"
streamlit run streamlit_app.py
```

The app opens automatically in your browser at: **http://localhost:8501**

To stop the app: press `Ctrl+C` in the terminal.

---

## 7. Using the App

### Tab 1: Knowledge Base Upload

1. Click **"Browse files"** → select a PDF, DOCX, or TXT
2. Click **"Process and Upload"**
3. Watch the progress bar as embeddings are generated
4. The document appears in the "Existing Documents" list below

### Tab 2: Chat

**Sidebar controls:**
- **Provider:** OpenAI or AWS Bedrock
- **Model:** Select GPT-4o, GPT-4o-mini, etc. (or Claude models for Bedrock)
- **Top K:** How many document chunks to retrieve (1-10, default 5)
- **Min Similarity:** Minimum relevance score (0.0-1.0, default 0.4)
- **Enhanced Embeddings:** Toggle for attribute-specific search

**Asking a question:**
1. Type your question in the text box
2. Click **Send**
3. Three columns appear with answers:
   - 🔵 **Without Context:** Pure AI knowledge (baseline)
   - 🟢 **With Context:** AI uses your uploaded documents
   - 🟡 **With Context + Guardrail:** Strictly uses only your documents

**Understanding the similarity scores:**
- Shown as `similarity: 0.750` — higher is more relevant
- Scores near 1.0 = very close match
- Scores below 0.4 are filtered out by default

---

## 8. All Code Files Explained

### `streamlit_app.py` — The Main App

The entry point. Runs the entire web UI.

**Key sections:**
| Lines | What it does |
|-------|-------------|
| 1-22 | Imports (including response generation functions) |
| 23-65 | Loads config from .env + defines model lists |
| 70-114 | Cached client factories (OpenAI, Bedrock, DB connection) |
| 120-175 | Database helper functions (store, get, delete documents) |
| 180-290 | Tab 1: Document upload UI |
| 290-595 | Tab 2: Chat UI + sidebar + 3-column response display |
| 420-470 | `search_similar_chunks()` — vector search helper |

---

### `document_utils.py` — Text Processing

**Functions:**

| Function | Input | Output |
|----------|-------|--------|
| `extract_text_from_pdf(bytes, filename)` | PDF bytes | Clean text string |
| `extract_text_from_docx(bytes)` | DOCX bytes | Clean text string |
| `extract_text_from_txt(bytes)` | Text bytes | Clean text string |
| `clean_extracted_text(text)` | Raw text | Normalized text |
| `chunk_text(text, size, overlap)` | Text + params | List of chunk dicts |

**Chunking algorithm:**
```
chunk_text("long text...", chunk_size=1000, overlap=200)

Returns:
[
  {"content": "first 1000 chars...", "start_pos": 0, "end_pos": 998},
  {"content": "chars 798-1800...",    "start_pos": 798, "end_pos": 1800},
  ...
]
```
- Tries to break at sentence boundaries (`. ` or `\n`) after 50% of chunk_size
- Each chunk overlaps the previous by `overlap` characters

---

### `embeddings_utils.py` — Vector Generation

**Functions:**

| Function | What it does |
|----------|-------------|
| `create_embedding(text, client)` | Single text → 1536-dim vector |
| `create_embeddings_batch(texts, client)` | List of texts → list of vectors (retries 3x with backoff) |
| `generate_enhanced_json(product, content, client)` | Uses GPT-4o-mini to extract structured JSON from a chunk |
| `generate_enhanced_embeddings_for_all(client)` | Generates enhanced versions of all uploaded chunks |

**Vector dimension:** 1536 (from `text-embedding-3-small` model)

---

### `response_generation.py` — LLM Integration

**Three response functions — all return `(answer: str, time: float)`:**

| Function | Temperature | Behavior |
|----------|-------------|---------|
| `generate_response_without_context(question, model, client, provider)` | 0.7 | No document context |
| `generate_response_with_context(question, chunks, model, client, provider)` | 0.7 | Uses all retrieved chunks, synthesizes |
| `generate_response_with_guardrail(question, chunks, model, client, provider)` | 0.3 | Strictly only uses provided context, refuses to use external knowledge |

**Provider support:**
- `provider="OpenAI"` → calls `client.chat.completions.create()`
- `provider="Bedrock"` → calls `client.invoke_model()` (boto3 bedrock-runtime)

---

### `scripts/setup_database.py` — Database Setup

Run **once** to create all tables, indexes, and grant permissions.

Creates:
- `company_documents` table
- `document_chunks` table (with 1536-dim vector column)
- `conversations` table
- HNSW vector index (fast similarity search)
- B-tree indexes on document_id, product_name, filename

---

## 9. Database Schema

### `company_documents` — Document Registry

```
id          | SERIAL PRIMARY KEY
filename    | VARCHAR(255)    — e.g., "product_spec.pdf"
file_type   | VARCHAR(50)     — "pdf", "docx", "txt"
file_path   | TEXT            — (empty string for uploaded files)
total_chunks| INTEGER         — how many chunks this doc has
uploaded_at | TIMESTAMP       — auto set on insert
metadata    | JSONB           — {"product_name": "AMI Meter"}
```

### `document_chunks` — Text + Vectors

```
id            | SERIAL PRIMARY KEY
document_id   | INTEGER → company_documents(id) ON DELETE CASCADE
chunk_index   | INTEGER         — 0, 1, 2... within the document
filename      | VARCHAR(255)
product_name  | VARCHAR(100)    — derived from filename (without extension)
content       | TEXT            — the actual chunk text
content_length| INTEGER
embedding     | vector(1536)    — the pgvector column
chunk_metadata| JSONB           — {"start_pos": 0, "end_pos": 998}
embedding_type| VARCHAR(20)     — "general" or "enhanced"
created_at    | TIMESTAMP
```

### `conversations` — Chat History

```
id            | SERIAL PRIMARY KEY
session_id    | UUID
user_question | TEXT
bot_response  | TEXT
chunks_used   | INTEGER[]       — IDs of chunks that were used
created_at    | TIMESTAMP
```

---

## 10. Bugs Fixed

The following bugs were found and fixed before this project can run:

| # | File | Bug | Fix Applied |
|---|------|-----|-------------|
| 1 | `streamlit_app.py` | `generate_response_*` functions used but never imported | Added `from response_generation import ...` |
| 2 | `streamlit_app.py` | Response functions return `(answer, time)` tuple but code treated them as plain strings — would display `('answer text', 0.42)` instead of just the answer | Changed to `ans, elapsed = generate_response_...()` |
| 3 | `streamlit_app.py` | `st.experimental_rerun()` deprecated in Streamlit 1.27+, raises `AttributeError` in newer versions | Replaced all 3 calls with `st.rerun()` |
| 4 | `streamlit_app.py` | boto3 `"bedrock"` service name is for management API — `invoke_model` requires `"bedrock-runtime"` | Changed to `"bedrock-runtime"` |
| 5 | `streamlit_app.py` | When Bedrock provider selected, Bedrock client was passed to embedding search — but embeddings always need OpenAI | Fixed to always use `openai_client` for embeddings |
| 6 | `embeddings_utils.py` | `from openai.error import OpenAIError` — old v0.x path, doesn't exist in openai>=1.0.0 | Changed to `from openai import OpenAIError` |
| 7 | `response_generation.py` | Same `openai.error` import bug | Same fix |
| 8 | `requirements.txt` | `pgvector>=0.5.2` — latest version is 0.4.2, install fails | Changed to `pgvector>=0.1.0` |

---

## 11. Environment Variables Reference

Create `.env` in the `rag-chatbot/` folder:

```env
# ── REQUIRED ──────────────────────────────────────────────
OPENAI_API_KEY=sk-proj-...          # Get from platform.openai.com/api-keys

# ── DATABASE ──────────────────────────────────────────────
DB_HOST=127.0.0.1                   # localhost
DB_PORT=5432                        # PostgreSQL default
DB_NAME=admin                       # database name you created
DB_USER=admin                       # database user you created
DB_PASSWORD=your_password           # password you set

# ── OPTIONAL: AWS Bedrock ─────────────────────────────────
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=ap-south-1

# ── OPTIONAL: Tuning ──────────────────────────────────────
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
LOG_LEVEL=INFO
```

---

## 12. Troubleshooting

### "connection refused" or DB errors
- Check PostgreSQL service is running: `services.msc` → look for `postgresql-x64-XX`
- Verify DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD in `.env`

### "OpenAI API key not found" / AuthenticationError
- Make sure `.env` file exists in the `rag-chatbot/` folder
- Check `OPENAI_API_KEY` is set correctly (no extra spaces)
- Make sure your OpenAI account has credits

### "vector type not found" or pgvector errors
- Run in psql: `CREATE EXTENSION IF NOT EXISTS vector;`
- pgvector must be installed for your PostgreSQL version

### "relation does not exist"
- Run the setup script: `python scripts/setup_database.py`

### App doesn't start
```bash
# Check Python version (need 3.9+)
python --version

# Check streamlit installed
pip show streamlit

# Try installing dependencies again
pip install -r requirements.txt
```

### "No relevant chunks found" in chat
- Make sure you uploaded at least one document in Tab 1
- Lower the "Min Similarity" slider (try 0.2 or 0.1)
- Increase "Top K" slider

---

## Quick Start Commands (All-in-One)

```bash
# 1. Navigate to project
cd "C:\Users\MDAliKhan\OneDrive - Sinhal Udyog pvt ltd\Desktop\ai\rag-chatbot"

# 2. Install packages
pip install -r requirements.txt

# 3. Create .env (copy template, then edit it)
copy .env.example .env
# → Open .env and fill in OPENAI_API_KEY + DB_PASSWORD

# 4. Create database tables (one-time)
python scripts/setup_database.py

# 5. Run the app
streamlit run streamlit_app.py
# → Opens at http://localhost:8501
```
