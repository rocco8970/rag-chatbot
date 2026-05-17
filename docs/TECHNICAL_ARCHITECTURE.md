# RAG Chatbot - Technical Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Data Flow](#data-flow)
4. [Technology Stack](#technology-stack)
5. [Core Modules](#core-modules)
6. [Embedding Strategy](#embedding-strategy)
7. [Vector Search Implementation](#vector-search-implementation)
8. [Response Generation Pipeline](#response-generation-pipeline)
9. [Security & Configuration](#security--configuration)
10. [Future Enhancements](#future-enhancements)

---

## System Overview

The RAG (Retrieval-Augmented Generation) Chatbot is a knowledge base system that combines document processing, local vector embeddings, semantic search, and free large language models to provide accurate, context-aware responses to user queries. It runs entirely on free APIs and local models — no paid services required.

### Key Capabilities
- Multi-format document ingestion (PDF, DOCX, TXT, MD, CSV)
- Intelligent text chunking with overlap
- Local embedding generation (no API key needed)
- Vector similarity search using ChromaDB
- Dual free LLM support (Google Gemini and Groq/Llama)
- Source attribution for every answer
- Real-time document management and statistics

### Architecture Pattern
The system follows the **RAG (Retrieval-Augmented Generation)** pattern:
1. Documents are processed and stored as vector embeddings in ChromaDB
2. User queries are converted to embeddings using the same local model
3. Similar document chunks are retrieved via cosine similarity search
4. Retrieved context is provided to a free LLM for response generation

---

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Web UI                        │
│  (streamlit_app.py)                                         │
│  - Document Upload Interface                                │
│  - Chat Interface with source attribution                   │
│  - LLM Provider Selection (Gemini / Groq)                  │
│  - Statistics Dashboard                                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├──────────────────┬──────────────────┐
                 │                  │                   │
        ┌────────▼────────┐ ┌──────▼──────┐  ┌────────▼────────┐
        │ Document Utils  │ │  Embeddings │  │    Response     │
        │ (document_      │ │    Utils    │  │   Generation    │
        │  utils.py)      │ │ (embeddings_│  │ (response_      │
        │                 │ │  utils.py)  │  │  generation.py) │
        │ - PDF (PyMuPDF) │ │ - Sentence  │  │ - Google Gemini │
        │ - DOCX          │ │   Transformers  - Groq / Llama  │
        │ - TXT / MD      │ │ - all-MiniLM│  │ - Prompt        │
        │ - CSV           │ │   -L6-v2    │  │   building      │
        │ - Chunking      │ │ - 384-dim   │  │ - Fallback      │
        │   (500/50)      │ │ - LOCAL     │  │   model logic   │
        └─────────────────┘ └─────────────┘  └─────────────────┘
                 │                  │                   │
                 └──────────────────┴───────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │          ChromaDB              │
                    │   (Persistent Vector Store)    │
                    │                                │
                    │  Collection: "documents"       │
                    │  - Text chunks                 │
                    │  - 384-dim embeddings          │
                    │  - Source metadata             │
                    │                                │
                    │  Index: cosine similarity      │
                    │  Path: ./chroma_db/            │
                    └────────────────────────────────┘
```

---

## Data Flow

### Document Upload Flow
```
1. User uploads document (PDF / DOCX / TXT / MD / CSV)
   ↓
2. Save to temporary file
   ↓
3. Extract text using format-specific parser
   ↓
4. Split into overlapping chunks (500 chars, 50 char overlap)
   ↓
5. Generate embeddings locally using Sentence Transformers
   ↓
6. Store chunks + embeddings + metadata in ChromaDB
   ↓
7. Display success with chunk count in sidebar
```

### Query Processing Flow
```
1. User submits question
   ↓
2. Generate query embedding using same local Sentence Transformers model
   ↓
3. Perform cosine similarity search in ChromaDB (top-k chunks)
   ↓
4. Join retrieved chunks into context string
   ↓
5. Build structured prompt (context + question + instructions)
   ↓
6. Send to selected LLM (Gemini or Groq) via free API
   ↓
7. Display answer with expandable source attribution
```

---

## Technology Stack

### Frontend
- **Streamlit 1.31+**: Web UI framework
  - Session state management for chat history and loaded models
  - File upload handling with progress indicators
  - Glass morphism custom CSS design

### Backend Processing
- **Python 3.9+**: Core language
- **PyMuPDF (fitz) 1.23+**: PDF text extraction
- **python-docx 1.1+**: DOCX parsing
- **pandas 2.1+**: CSV handling

### AI / ML — All Free
- **Sentence Transformers 2.5+** (local, no API key):
  - Model: `all-MiniLM-L6-v2`
  - Output: 384-dimensional vectors
  - Runs entirely on local CPU/GPU
- **Google Gemini API** (free tier):
  - Primary model: `gemini-2.5-flash`
  - Fallback chain: `gemini-2.0-flash` → `gemini-2.0-flash-001` → `gemini-2.0-flash-lite`
- **Groq API** (free tier):
  - Model: `llama-3.1-8b-instant`
  - Ultra-fast inference

### Vector Database
- **ChromaDB 0.4+**: Persistent vector store
  - Cosine similarity metric (`hnsw:space: cosine`)
  - Stored locally at `./chroma_db/`
  - No external server required

### Configuration
- **python-dotenv 1.0+**: Environment variable management

---

## Core Modules

### 1. Document Processing (`document_utils.py`)

#### `DocumentProcessor`
Handles text extraction from all supported formats:

| Format | Library | Notes |
|--------|---------|-------|
| PDF | PyMuPDF (fitz) | Multi-page, extracts all text blocks |
| DOCX | python-docx | Paragraphs and tables |
| TXT / MD | Built-in | UTF-8 with latin-1 fallback |
| CSV | pandas | Converts rows to readable text |

#### `TextChunker`
```
Parameters: chunk_size=500, chunk_overlap=50

Algorithm:
1. Walk through text in steps of (chunk_size - chunk_overlap)
2. Extract windows of chunk_size characters
3. Consecutive chunks share 50 characters of overlap
4. Returns list of text strings
```

**Why overlap?** Ensures that a sentence split across a chunk boundary is still present in full in at least one chunk, preserving context for retrieval.

---

### 2. Embeddings (`embeddings_utils.py`)

#### `EmbeddingsManager`
```python
Model: sentence-transformers/all-MiniLM-L6-v2
Dimensions: 384
Device: auto-detected (CPU / CUDA)
```

Key methods:
- `get_embeddings(texts: List[str]) → np.ndarray` — batch encode document chunks
- `get_query_embedding(query: str) → np.ndarray` — encode a single user query

**Why local embeddings?** No API key, no cost, no rate limits. The `all-MiniLM-L6-v2` model is small (~80MB) but produces high-quality semantic embeddings suitable for document retrieval.

---

### 3. Response Generation (`response_generation.py`)

#### `ResponseGenerator`
Supports two free LLM providers with a unified interface:

**Gemini provider:**
```python
Client: google.genai.Client
Model chain (with automatic fallback):
  gemini-2.5-flash → gemini-2.0-flash → gemini-2.5-pro
  → gemini-2.0-flash-001 → gemini-2.0-flash-lite
```

**Groq provider:**
```python
Client: groq.Groq
Model: llama-3.1-8b-instant
Temperature: 0.7
Max tokens: 1024
```

#### Prompt Template
```
You are a helpful AI assistant. Answer the question based ONLY on the
context provided below. If the answer is not in the context, say
"I don't have enough information to answer this question."

CONTEXT:
{retrieved_chunks_joined}

QUESTION:
{user_question}

INSTRUCTIONS:
- Provide a clear, concise answer
- Use bullet points if listing multiple items
- Cite specific information from the context
- Be helpful and friendly

ANSWER:
```

---

### 4. RAG Pipeline (`rag_pipeline.py`)

The `RAGPipeline` class orchestrates all components end-to-end:

```python
pipeline = RAGPipeline(llm_provider="gemini")
pipeline.ingest_document("myfile.pdf")   # process + store
result = pipeline.query("What is X?")    # retrieve + generate
stats  = pipeline.get_stats()            # usage stats
pipeline.clear_all()                     # reset database
```

The Streamlit app implements the same logic inline using `st.session_state` for persistence across page interactions.

---

### 5. Evaluation (`evaluation.py`)

#### `RAGEvaluator`
Measures retrieval quality with keyword-based recall:

```python
evaluate_retrieval(query, expected_keywords):
    recall = keywords_found_in_retrieved_text / total_keywords
```

Saves full evaluation results to `evaluation/eval_results.json`.

---

## Embedding Strategy

### Vector Representation
- **Model**: `all-MiniLM-L6-v2` (Sentence Transformers)
- **Dimensions**: 384
- **Metric**: Cosine similarity
- **Storage**: ChromaDB persistent collection

### Why Cosine Similarity?
Cosine similarity measures the angle between two vectors regardless of magnitude. This makes it robust to differences in document length — a short query and a long chunk can still match well if they discuss the same topic.

### Embedding at Query Time
The same model is used for both document chunks and user queries, ensuring vectors live in the same semantic space and similarity scores are meaningful.

---

## Vector Search Implementation

### ChromaDB Configuration
```python
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"}
)
```

ChromaDB uses an HNSW (Hierarchical Navigable Small World) index internally for fast approximate nearest neighbour search.

### Adding Documents
```python
collection.add(
    documents=chunks,          # raw text (for display)
    embeddings=embeddings,     # 384-dim float lists
    metadatas=metadatas,       # source filename, chunk index, timestamp
    ids=ids                    # unique UUIDs
)
```

### Querying
```python
results = collection.query(
    query_embeddings=[query_vector],
    n_results=top_k            # default 5, configurable 1–10 in UI
)
# Returns: documents, metadatas, distances
```

### Search Parameters
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `top_k` | 5 | 1–10 | Number of chunks to retrieve |
| `chunk_size` | 500 | — | Characters per chunk |
| `chunk_overlap` | 50 | — | Shared characters between consecutive chunks |

---

## Response Generation Pipeline

### Context Building
Retrieved chunks are joined with double newlines:
```python
context = "\n\n".join(results["documents"][0])
```

### Source Attribution
Each chunk's metadata (`source`, `chunk_index`) is returned alongside the answer and displayed to the user in an expandable "View sources" section.

### Provider Fallback (Gemini)
The Gemini provider tries models in sequence and stops at the first success:
```
gemini-2.5-flash → gemini-2.0-flash → gemini-2.5-pro
→ gemini-2.0-flash-001 → gemini-2.0-flash-lite → gemini-flash-latest
```
This ensures the app stays functional even if a specific model version becomes unavailable on your API key tier.

---

## Security & Configuration

### Environment Variables (`.env`)
```bash
# LLM Providers (free tier)
GEMINI_API_KEY=your_gemini_key_here
GROQ_API_KEY=your_groq_key_here

# Default provider
LLM_PROVIDER=gemini

# RAG parameters
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K=5
```

### Security Best Practices
1. **Never commit `.env`** — it is listed in `.gitignore`
2. **Use `.env.example`** as the template for sharing setup instructions
3. **API keys are read-only at runtime** via `python-dotenv`
4. **ChromaDB is local** — no network exposure of your documents

### Session State Caching
Expensive objects are initialised once per browser session:
```python
# Embeddings model loaded once (~1 min first time)
st.session_state.embeddings_manager = EmbeddingsManager()

# LLM clients created once per provider, reused across queries
st.session_state.response_generators[provider] = ResponseGenerator(provider)
```

---

## Performance Considerations

### Embedding Generation
- Model loads once into memory at app startup
- Subsequent uploads embed chunks in a single batch call
- No API calls or internet needed for embeddings

### LLM Latency
- **Groq**: Typically 1–3 seconds (optimised hardware inference)
- **Gemini**: Typically 2–5 seconds (free tier)

### ChromaDB
- Persistent storage means embeddings survive app restarts
- HNSW index makes similarity search sub-second even for thousands of chunks

---

## Future Enhancements

1. **Hybrid search**: Combine vector search with BM25 keyword search for better recall
2. **Streaming responses**: Stream LLM tokens to the UI instead of waiting for full response
3. **Reranking**: Add a cross-encoder reranker after retrieval for better precision
4. **Conversation memory**: Pass last N exchanges to the LLM for follow-up questions
5. **Multi-modal**: Support images and tables extracted from PDFs
6. **Export**: Allow downloading conversation history as PDF or text

---

## Conclusion

This RAG chatbot is built entirely on free, open tools:
- **Local embeddings** via Sentence Transformers (no API cost)
- **Free LLM APIs** via Google Gemini and Groq
- **Embedded vector database** via ChromaDB (no external server)

The modular design (`document_utils`, `embeddings_utils`, `response_generation`, `rag_pipeline`) makes each component independently testable and replaceable — for example, swapping ChromaDB for FAISS or adding a new LLM provider requires changes to only one module.
