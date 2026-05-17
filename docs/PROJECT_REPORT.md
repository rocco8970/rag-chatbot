# Project Report: RAG-Based Intelligent Document Q&A System

> **Degree Programme:** B.Tech / MCA, Computer Science  
> **University:** Jamia Hamdard, New Delhi  
> **Department:** Department of Computer Science  
> **Academic Year:** 2024–25  

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Problem Statement](#2-problem-statement)
3. [Objectives](#3-objectives)
4. [Introduction to RAG](#4-introduction-to-rag)
5. [System Architecture](#5-system-architecture)
6. [Algorithms and Techniques Used](#6-algorithms-and-techniques-used)
7. [Technology Stack — What Was Used and Why](#7-technology-stack--what-was-used-and-why)
8. [Module-wise Implementation](#8-module-wise-implementation)
9. [Both Frontend Implementations](#9-both-frontend-implementations)
10. [How It Is Helpful](#10-how-it-is-helpful)
11. [Evaluation and Testing](#11-evaluation-and-testing)
12. [Challenges and Solutions](#12-challenges-and-solutions)
13. [Limitations and Future Work](#13-limitations-and-future-work)
14. [Conclusion](#14-conclusion)
15. [References](#15-references)

---

## 1. Abstract

This project presents a **Retrieval-Augmented Generation (RAG) based chatbot** capable of answering questions from user-uploaded documents with accurate source attribution. The system processes documents in multiple formats (PDF, DOCX, TXT, CSV, Markdown), converts them into dense vector representations using a locally-run transformer model, stores these vectors in a persistent vector database, and retrieves the most semantically relevant content when a user poses a question. The retrieved context is then passed to a free large language model (Google Gemini or Groq Llama) to generate a grounded, human-readable answer.

The project is implemented in Python and delivered through two interfaces: an original Streamlit-based UI and a modern React + FastAPI UI with real-time token streaming via WebSocket. All components use **free and open-source tools** — no paid API subscriptions are required for core functionality. The embedding model runs entirely locally, meaning documents are never sent to any external server for vectorisation.

---

## 2. Problem Statement

Traditional search engines return lists of links or document excerpts based on keyword matching. This approach has several shortcomings:

- **Lacks natural language understanding** — "power consumption" and "how much electricity does it use" return different results
- **No synthesis** — users must read multiple documents and draw their own conclusions
- **No grounding** — generic AI chatbots (like raw GPT) answer from training data, which may be outdated, incorrect, or irrelevant to the user's specific documents
- **Hallucination** — language models can generate confident-sounding but factually wrong answers when they lack reliable context

**The challenge:** How can we build a system that answers questions in natural language, uses the user's own documents as the authoritative source, and avoids hallucination?

---

## 3. Objectives

1. Design and implement a full RAG pipeline that processes user documents and answers questions from them
2. Use only free APIs and locally-run models to demonstrate cost-effectiveness
3. Provide accurate source attribution so users can verify every answer
4. Implement semantic search (not keyword search) for better retrieval quality
5. Build two functional interfaces — a simple Streamlit UI and a modern React UI with streaming
6. Evaluate retrieval quality using recall metrics

---

## 4. Introduction to RAG

### What is RAG?

**Retrieval-Augmented Generation (RAG)** is an AI architecture that combines two approaches:

1. **Retrieval** — searching a knowledge base for relevant information
2. **Generation** — using a large language model to compose a human-readable answer

Introduced by Lewis et al. (2020) at Facebook AI Research, RAG addresses the fundamental limitation of language models: their knowledge is frozen at training time. RAG allows a model to access up-to-date, domain-specific, or private information at query time.

### Why RAG over pure LLM?

| Approach | Knowledge source | Accuracy for specific docs | Hallucination risk |
|----------|-----------------|---------------------------|-------------------|
| Pure LLM | Training data (fixed) | Low | High |
| Fine-tuning | Retrained on new data | Medium | Medium |
| **RAG** | **Live retrieval from documents** | **High** | **Low** |

### How RAG works — the core idea

```
Documents → Vectors (stored in database)
                    ↓
Query → Vector → Similar document vectors found
                    ↓
Context (retrieved chunks) + Query → LLM → Grounded Answer
```

The critical insight is that the LLM is only asked to *compose an answer from already-retrieved context*, not to recall facts from memory. This dramatically reduces hallucination.

---

## 5. System Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────┐
│              User Interface                    │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │  Streamlit UI    │  │  React 18 UI     │   │
│  │  (streamlit_     │  │  (frontend/)     │   │
│  │   app.py)        │  │                  │   │
│  └────────┬─────────┘  └────────┬─────────┘   │
└───────────┼──────────────────────┼─────────────┘
            │                      │ HTTP/WebSocket
            │              ┌───────▼──────────┐
            │              │  FastAPI Backend  │
            │              │  (backend/main.py)│
            │              └───────┬───────────┘
            │                      │
            └──────────────────────┘
                         │
            ┌────────────▼────────────────────┐
            │         RAG Pipeline (src/)      │
            │                                  │
            │  document_utils.py               │
            │  ↓ extract + chunk               │
            │  embeddings_utils.py             │
            │  ↓ encode to vectors             │
            │  rag_pipeline.py                 │
            │  ↓ orchestrate                   │
            │  response_generation.py          │
            │  ↓ call LLM                      │
            └────────────┬────────────────────┘
                         │
            ┌────────────▼────────────────────┐
            │     ChromaDB (Vector Store)      │
            │     ./chroma_db/ (persistent)    │
            │                                  │
            │  Collection: "documents"         │
            │  Metric: cosine similarity       │
            │  Index: HNSW                     │
            └─────────────────────────────────┘
                         ↕
            ┌────────────────────────────────┐
            │   External Free LLM APIs       │
            │  ┌─────────────────────────┐   │
            │  │ Google Gemini 2.5 Flash  │   │
            │  └─────────────────────────┘   │
            │  ┌─────────────────────────┐   │
            │  │ Groq Llama 3.1-8b       │   │
            │  └─────────────────────────┘   │
            └────────────────────────────────┘
```

### Data Flow — Document Ingestion

```
Step 1: User uploads file
        ↓
Step 2: DocumentProcessor extracts raw text
        (PyMuPDF for PDF, python-docx for DOCX, pandas for CSV)
        ↓
Step 3: TextChunker splits into overlapping chunks
        chunk_size=500 chars, overlap=50 chars
        ↓
Step 4: EmbeddingsManager encodes each chunk
        Model: all-MiniLM-L6-v2 (local)
        Output: 384-dimensional float vector per chunk
        ↓
Step 5: ChromaDB stores (text, vector, metadata)
        metadata = {source, chunk_index, timestamp}
```

### Data Flow — Query and Answer

```
Step 1: User types question
        ↓
Step 2: EmbeddingsManager encodes the question
        Same model → same vector space → comparable to document vectors
        ↓
Step 3: ChromaDB cosine similarity search
        Finds top-K chunks with smallest angular distance to query vector
        ↓
Step 4: Context string built from retrieved chunks
        ↓
Step 5: Prompt assembled:
        "Answer ONLY from context: [chunks] \n Question: [query]"
        ↓
Step 6: Prompt sent to Gemini or Groq API
        ↓
Step 7: Answer returned with source metadata
```

---

## 6. Algorithms and Techniques Used

### 6.1 Text Chunking with Sliding Window

**Problem:** LLMs have a context window limit. A 100-page document cannot be sent as-is.

**Solution:** Split text into small, overlapping windows.

**Algorithm:**
```python
for i in range(0, len(text), chunk_size - overlap):
    chunk = text[i : i + chunk_size]
    chunks.append(chunk)
```

**Why overlap?** If a sentence spans the boundary between two chunks, the overlap ensures it is fully present in at least one chunk. Without overlap, context at chunk boundaries is lost.

**Parameters used:** chunk_size=500, overlap=50

---

### 6.2 Dense Vector Embeddings (Transformer-based)

**What is an embedding?** A dense vector (list of floats) representing the semantic meaning of a piece of text. Two texts with similar meaning produce vectors that are close together in the vector space.

**Model used:** `all-MiniLM-L6-v2` from Sentence Transformers

This is a **BERT-based transformer model** distilled from a larger model for speed while retaining strong semantic quality.

**Architecture:**
```
Text → Tokenisation → BERT Encoder (6 layers) → Mean Pooling → 384-dim vector
```

**Why 384 dimensions?** Each dimension captures a different aspect of meaning. 384 is a good trade-off between quality and memory/speed.

**Key property:** The same model encodes both documents and queries, ensuring they live in the same vector space for meaningful comparison.

**Example:**
```
"The device supports 230V input" → [0.12, -0.45, 0.78, ...]   (384 floats)
"What voltage does it support?"  → [0.14, -0.43, 0.76, ...]   (384 floats)
                                    ↑ very similar vectors → high cosine similarity
```

---

### 6.3 Cosine Similarity

**Purpose:** Measure how similar two vectors are, regardless of their magnitude.

**Formula:**
```
cosine_similarity(A, B) = (A · B) / (|A| × |B|)
```

Where A · B is the dot product and |A|, |B| are the magnitudes (lengths) of the vectors.

**Result:** A score between -1 and 1, where:
- `1.0` = identical direction (same meaning)
- `0.0` = orthogonal (unrelated)
- `-1.0` = opposite meaning

**Why cosine over Euclidean distance?** Cosine similarity is invariant to vector length. A short summary and a long paragraph about the same topic will have similar cosine similarity to a query, even though their Euclidean distance might be large (because the longer paragraph's vector has larger magnitude).

ChromaDB uses `hnsw:space: cosine` which is configured at collection creation:
```python
collection = client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"}
)
```

---

### 6.4 HNSW (Hierarchical Navigable Small World) Index

**Problem:** Brute-force similarity search requires comparing every query to every stored vector — O(n) time. For thousands of chunks, this is too slow.

**Solution:** HNSW is an **Approximate Nearest Neighbour (ANN)** algorithm that builds a multi-layer graph structure allowing fast sub-linear search.

**How it works:**
- Documents are inserted into a graph where each node (chunk) is connected to its nearest neighbours
- The graph has multiple layers — higher layers have fewer nodes (long-range connections), lower layers are dense (fine-grained)
- At query time, the search starts at the top layer and descends through layers, following the best connections at each step
- This finds the approximate nearest neighbours in O(log n) time

**Why HNSW?** It is the standard algorithm used by systems like FAISS (Facebook), Weaviate, Pinecone, and ChromaDB for fast vector search. It achieves >99% recall of true nearest neighbours while being orders of magnitude faster than brute force.

ChromaDB uses HNSW internally — it is configured via `metadata={"hnsw:space": "cosine"}`.

---

### 6.5 Prompt Engineering

**What is prompt engineering?** Carefully designing the text given to an LLM to elicit accurate, constrained, and useful responses.

**The prompt template used in this project:**
```
You are a helpful AI assistant. Answer the question based ONLY on the
context provided below. If the answer is not in the context, say
"I don't have enough information to answer this question."

CONTEXT:
{retrieved_chunks}

QUESTION:
{user_question}

INSTRUCTIONS:
- Provide a clear, concise answer
- Use bullet points if listing multiple items
- Cite specific information from the context
- Be helpful and friendly

ANSWER:
```

**Key design decisions:**
- `"Answer based ONLY on the context"` — prevents the LLM from mixing in its training knowledge, reducing hallucination
- `"If the answer is not in the context, say..."` — teaches the model to acknowledge missing information rather than invent an answer
- The `INSTRUCTIONS` section improves formatting consistency

---

### 6.6 WebSocket Token Streaming

**What is streaming?** Instead of waiting for the complete LLM response before displaying anything, streaming sends each generated token (word/sub-word) to the client as it is produced.

**Why it matters:** For a 200-word response, streaming means users start reading in 0.5 seconds instead of waiting 3-5 seconds for the full response.

**How it is implemented:**

Server side (FastAPI):
```python
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    # ...retrieve context...
    for token in generator.stream_response(question, context):
        await websocket.send_json({"token": token, "done": False})
    await websocket.send_json({"done": True, "sources": sources})
```

Client side (React):
```javascript
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (!data.done) {
        // append token to displayed message
        setMessages(prev => {
            const last = prev[prev.length - 1];
            return [...prev.slice(0,-1), {...last, content: last.content + data.token}];
        });
    }
};
```

The Gemini and Groq APIs both support streaming:
- Gemini: `client.models.generate_content_stream()`
- Groq: `client.chat.completions.create(stream=True)`

---

### 6.7 RAG Evaluation — Retrieval Recall

**How to measure if retrieval is working well?**

The project includes an evaluator (`src/evaluation.py`) that measures **retrieval recall**:

```
recall = number_of_expected_keywords_found_in_retrieved_chunks
         ÷ total_expected_keywords
```

A recall of 1.0 means the retrieval found all the information needed to answer a test question. A recall of 0.5 means it found half.

This is important for academic evaluation because it separates the retrieval quality from the LLM generation quality — you can improve them independently.

---

## 7. Technology Stack — What Was Used and Why

### 7.1 Python (Core Language)

Python was chosen for its rich ecosystem of AI/ML libraries, fast prototyping capability, and direct integration with every major LLM provider's SDK.

### 7.2 Sentence Transformers — `all-MiniLM-L6-v2`

| Property | Value |
|----------|-------|
| Type | Pre-trained transformer (BERT-based) |
| Dimensions | 384 |
| Cost | Free (runs locally) |
| Model size | ~80 MB |
| Speed | ~2000 sentences/second on CPU |

**Why this model over others?** It is specifically trained with contrastive learning on pairs of similar sentences, making it excellent for semantic similarity tasks. It is the most widely used model for retrieval-based systems with limited compute. It outperforms bag-of-words and TF-IDF by a large margin on semantic search benchmarks.

### 7.3 ChromaDB

| Property | Value |
|----------|-------|
| Type | Embedded vector database |
| Storage | Local disk (`./chroma_db/`) |
| Index | HNSW (approximate nearest neighbour) |
| Similarity | Cosine |
| Cost | Free, open-source |

**Why ChromaDB over alternatives (FAISS, Pinecone, Weaviate)?**
- **vs FAISS:** ChromaDB adds metadata storage, persistence, and a simple Python API on top of FAISS-like indexing. No manual file management needed.
- **vs Pinecone/Weaviate:** These require cloud accounts or Docker. ChromaDB runs as a Python library — no external services.
- For a college project, simplicity and zero infrastructure requirements make ChromaDB ideal.

### 7.4 Google Gemini API (Free Tier)

| Property | Value |
|----------|-------|
| Model | gemini-2.5-flash |
| Cost | Free (up to rate limits) |
| Context window | 1 million tokens |
| Streaming | Supported |

Gemini 2.5 Flash is one of the most capable free-tier models available as of 2025. The project implements automatic fallback through multiple model versions, so it continues to work even if a specific version has rate-limit issues.

### 7.5 Groq API (Free Tier)

| Property | Value |
|----------|-------|
| Model | llama-3.1-8b-instant |
| Cost | Free (up to rate limits) |
| Speed | ~500 tokens/second (extremely fast) |
| Streaming | Supported |

Groq uses custom hardware (LPU — Language Processing Unit) to achieve inference speeds significantly faster than GPU-based providers. It is an excellent alternative to Gemini, especially for quick responses.

### 7.6 FastAPI

FastAPI is a modern Python web framework built on Starlette and Pydantic. It was chosen for the backend because:
- **WebSocket support** — native async WebSocket handlers for streaming
- **Auto documentation** — Swagger UI available at `/docs` automatically
- **Performance** — ASGI-based, comparable to Node.js for I/O-bound tasks
- **Type safety** — Pydantic models validate request/response data

### 7.7 React 18 + Vite

React 18 provides the component model for the frontend UI. Key libraries used:

| Library | Purpose |
|---------|---------|
| Vite | Build tool and dev server (replaces Webpack — much faster) |
| Tailwind CSS v4 | Utility-first CSS for styling without writing custom CSS |
| Framer Motion | Declarative animations (message fade-in, bounce indicators) |
| React Icons | SVG icon library |
| Axios | HTTP client for REST API calls |
| React Markdown | Renders markdown syntax in bot responses |

### 7.8 Streamlit (Original UI)

Streamlit allows building web UIs entirely in Python without any JavaScript. The original UI uses Streamlit for:
- File upload widgets
- Chat input and output rendering
- Session state for persisting models and history
- Custom CSS for the glass-morphism dark theme

---

## 8. Module-wise Implementation

### Module 1: Document Processing (`src/document_utils.py`)

**Input:** File path (any supported format)  
**Output:** Clean text string + metadata dict

The `DocumentProcessor` class uses format detection (file extension) to route to the correct parser:

```
PDF  → PyMuPDF (fitz) — extracts text blocks page by page
DOCX → python-docx — iterates paragraphs and table cells
CSV  → pandas.read_csv().to_string() — converts tabular data to text
TXT/MD → open(path, 'r') with UTF-8 / latin-1 fallback
```

The `TextChunker` class implements sliding-window chunking with configurable `chunk_size` and `chunk_overlap`.

### Module 2: Embeddings (`src/embeddings_utils.py`)

**Input:** List of text strings  
**Output:** NumPy array of shape (n, 384)

Uses `SentenceTransformer('all-MiniLM-L6-v2')`. The model is downloaded on first run (~80MB) and cached in `~/.cache/torch/sentence_transformers/`. Subsequent calls are instant.

Two public methods:
- `get_embeddings(texts)` → batch encode (used during document ingestion)
- `get_query_embedding(text)` → single encode (used during query)

### Module 3: Response Generation (`src/response_generation.py`)

**Input:** Question + context string  
**Output:** Answer string (or token generator for streaming)

The `ResponseGenerator` class abstracts both Gemini and Groq behind a unified interface. Provider is set at construction time and cached in session state to avoid re-initialising API clients on every request.

### Module 4: RAG Pipeline (`src/rag_pipeline.py`)

**Input:** File path (ingest) or question string (query)  
**Output:** Ingestion result dict or answer + sources dict

The `RAGPipeline` class glues all three modules together and manages the ChromaDB connection. Each document chunk is stored with metadata:
```python
{
    "source": "filename.pdf",
    "chunk_index": 0,
    "ingested_at": "2026-05-18T10:30:00"
}
```

### Module 5: Evaluation (`src/evaluation.py`)

**Input:** Test cases with expected keywords  
**Output:** Recall scores + JSON report

The `RAGEvaluator` measures how well the retrieval step works independently of the LLM step. Saves results to `evaluation/eval_results.json` for academic reporting.

---

## 9. Both Frontend Implementations

### 9.1 Streamlit UI

**File:** `streamlit_app.py`  
**Run:** `streamlit run streamlit_app.py`  
**URL:** http://localhost:8501

Built in pure Python using Streamlit. Custom CSS achieves a dark glass-morphism design.

Key Streamlit patterns used:
- `st.session_state` — persists objects across page rerenders
- `st.file_uploader()` — multi-file upload widget
- `st.chat_input()` — chat input box
- `st.spinner()` — loading indicator
- `st.rerun()` — force page re-render after state change

### 9.2 React + FastAPI UI

**Backend:** `backend/main.py` — FastAPI  
**Frontend:** `frontend/` — React 18 + Vite  
**Run:** uvicorn on port 8000 + npm run dev on port 5173

The Vite proxy forwards `/api/*` to FastAPI port 8000 and `/ws/*` as WebSocket connections, so the React app can call the backend without CORS issues during development.

**Component tree:**
```
App.jsx
├── Sidebar.jsx
│   ├── Stats cards (GET /api/stats)
│   ├── Model selector buttons
│   ├── File upload (POST /api/upload via Axios)
│   ├── Document list (GET /api/documents)
│   └── Clear button (DELETE /api/documents)
└── ChatWindow.jsx
    ├── Message list
    │   └── Message.jsx × n
    │       ├── User bubble
    │       ├── Bot bubble (ReactMarkdown)
    │       └── Sources expander
    ├── Typing indicator (Framer Motion)
    └── Input bar (WebSocket /ws/chat)
```

---

## 10. How It Is Helpful

### Academic Use Cases

- **Research assistant:** Upload research papers and ask "What methodology did the authors use?" or "Summarise the results section"
- **Study helper:** Upload lecture notes and ask questions for revision
- **Literature review:** Upload multiple papers and ask "What do all these papers say about [topic]?"

### Professional Use Cases

- **HR / Documentation:** Upload company policies and ask "What is the leave policy?"
- **Technical support:** Upload product manuals and answer customer questions instantly
- **Legal / Compliance:** Upload regulations and ask "What does the document say about data retention?"
- **Customer service:** Upload FAQs and product documentation as a self-service chatbot

### Key Benefits Over Regular Search

| Regular Search | RAG Chatbot |
|---------------|-------------|
| Returns document excerpts | Returns composed answers in natural language |
| Keyword matching | Semantic similarity (understands meaning) |
| User must read and interpret | Answer is already synthesised |
| No source grounding | Every answer shows exactly which chunk it came from |
| Works on web only | Works on your private documents |

### Zero Cost

- **Embeddings:** Sentence Transformers runs locally — no API cost
- **Vector database:** ChromaDB is open-source — no hosting cost
- **LLMs:** Gemini and Groq both offer free tiers sufficient for a college project
- **Total API cost for typical project use:** ₹0

---

## 11. Evaluation and Testing

### Retrieval Evaluation

The `RAGEvaluator` class measures **retrieval recall** — whether the retrieval step finds the right content before the LLM even sees it.

```python
test_cases = [
    {
        "question": "What is RAG?",
        "expected_keywords": ["retrieval", "generation", "augmented"]
    }
]
results = evaluator.run_test_suite(test_cases)
# results["average_recall"] = 0.95 means 95% of expected keywords found
```

### Unit Tests

- `tests/test_app.py` — tests Streamlit app components
- `tests/test_database.py` — tests ChromaDB connectivity

### Manual Testing Procedure

1. Upload a known document
2. Ask questions whose answers are explicitly in the document
3. Verify the answer matches the document content
4. Check the sources expander to confirm the correct chunk was retrieved
5. Test edge case: ask a question whose answer is NOT in the document — verify the system says "I don't have enough information"

### Benchmark: Embedding Model

The `all-MiniLM-L6-v2` model scores **0.669** on the SBERT benchmarks (Semantic Textual Similarity tasks), compared to 0.612 for traditional TF-IDF and 0.421 for BM25 keyword search. This demonstrates the clear advantage of using transformer-based embeddings over older keyword-based approaches.

---

## 12. Challenges and Solutions

### Challenge 1: Context Window Limits

**Problem:** LLMs have token limits. A full document often exceeds this limit.

**Solution:** Chunking with overlap. Only the top-K most relevant chunks (not the whole document) are sent to the LLM, keeping the prompt within token limits.

### Challenge 2: Context Boundary Loss

**Problem:** A sentence split across two chunks loses its full context in both halves.

**Solution:** 50-character overlap between consecutive chunks ensures sentences at boundaries appear complete in at least one chunk.

### Challenge 3: Free Tier API Reliability

**Problem:** Free tier LLM APIs occasionally return errors or rate-limit responses.

**Solution:** Gemini provider implements an automatic model fallback chain — if `gemini-2.5-flash` fails, it automatically tries `gemini-2.0-flash`, then `gemini-2.0-flash-001`, etc. Groq is available as a full alternative provider.

### Challenge 4: API Client Re-initialisation

**Problem:** Re-creating the `ResponseGenerator` (which initialises the API client) on every question added unnecessary latency.

**Solution:** `ResponseGenerator` instances are cached in `st.session_state.response_generators` (Streamlit) and `app.state.generators` (FastAPI), keyed by provider name. They are only created once per provider per session.

### Challenge 5: Scanned PDF Support

**Problem:** PDFs that are scanned images (not text-based) return empty strings from PyMuPDF.

**Current limitation:** OCR (Optical Character Recognition) is not implemented. Users are advised to use text-based PDFs.

---

## 13. Limitations and Future Work

### Current Limitations

| Limitation | Impact |
|-----------|--------|
| Scanned PDF (image-based) not supported | Cannot process non-text PDFs |
| No multi-turn memory | Each question is independent; no follow-up context |
| Keyword-only recall evaluation | No response quality metric (BLEU, ROUGE) |
| No user authentication | Anyone with access to the URL can use the system |
| Single-language support | Best performance with English documents |

### Planned Future Enhancements

1. **Hybrid search:** Combine dense vector search with BM25 keyword search using Reciprocal Rank Fusion (RRF) for better recall
2. **Conversation memory:** Include last N chat turns in the prompt to support follow-up questions
3. **OCR support:** Integrate Tesseract or PaddleOCR for scanned PDF support
4. **Reranking:** Add a cross-encoder (e.g., `ms-marco-MiniLM-L-6-v2`) to rerank retrieved chunks for better precision
5. **Response evaluation:** Add RAGAS metrics (faithfulness, relevance, context precision) for automated quality assessment
6. **Multi-language support:** Swap embedding model for multilingual variant (`paraphrase-multilingual-MiniLM-L12-v2`)
7. **Authentication:** Add user login so document spaces are kept separate per user

---

## 14. Conclusion

This project successfully implements a complete RAG (Retrieval-Augmented Generation) pipeline that allows users to upload documents in multiple formats and receive accurate, source-attributed answers to natural language questions.

Key accomplishments:
- **Zero-cost implementation** using free APIs (Gemini, Groq) and local models (Sentence Transformers)
- **Semantic search** via 384-dimensional transformer embeddings and HNSW-indexed cosine similarity in ChromaDB — significantly superior to keyword search
- **Anti-hallucination design** through prompt engineering that constrains the LLM to answer only from retrieved context
- **Two functional UIs:** an original Streamlit application and a modern React + FastAPI application with real-time WebSocket streaming
- **Modular architecture:** the `src/` pipeline is completely independent of the UI layer, making it easy to test, maintain, and extend

The project demonstrates practical application of several key concepts from the computer science curriculum: information retrieval, natural language processing, transformer models, vector databases, REST APIs, and web development. It combines these concepts into a production-quality application that solves a real-world problem — making document knowledge accessible through natural language.

---

## 15. References

1. **Lewis, P., et al.** (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.* NeurIPS 2020. Facebook AI Research. https://arxiv.org/abs/2005.11401

2. **Reimers, N., & Gurevych, I.** (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks.* EMNLP 2019. https://arxiv.org/abs/1908.10084

3. **Malkov, Y. A., & Yashunin, D. A.** (2018). *Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs.* IEEE Transactions on Pattern Analysis and Machine Intelligence. https://arxiv.org/abs/1603.09320

4. **Chroma.** (2024). *ChromaDB: The open-source embedding database.* https://www.trychroma.com

5. **Google.** (2025). *Gemini API Documentation.* https://ai.google.dev

6. **Groq.** (2025). *Groq API Documentation.* https://console.groq.com/docs

7. **Vaswani, A., et al.** (2017). *Attention Is All You Need.* NeurIPS 2017. https://arxiv.org/abs/1706.03762 (Foundation of transformer models used in Sentence Transformers)

8. **Sbert.net Benchmarks.** (2024). *Pretrained Models.* https://www.sbert.net/docs/pretrained_models.html

9. **FastAPI Documentation.** (2025). https://fastapi.tiangolo.com

10. **Streamlit Documentation.** (2025). https://docs.streamlit.io
