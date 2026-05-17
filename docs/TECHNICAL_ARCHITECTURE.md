# RAG Chatbot - Technical Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Components](#architecture-components)
3. [Data Flow](#data-flow)
4. [Technology Stack](#technology-stack)
5. [Database Schema](#database-schema)
6. [Core Modules](#core-modules)
7. [Embedding Strategy](#embedding-strategy)
8. [Vector Search Implementation](#vector-search-implementation)
9. [Response Generation Pipeline](#response-generation-pipeline)
10. [Security & Configuration](#security--configuration)

---

## System Overview

The RAG (Retrieval-Augmented Generation) Chatbot is a production-ready knowledge base system that combines document processing, vector embeddings, semantic search, and large language models to provide accurate, context-aware responses to user queries.

### Key Capabilities
- Multi-format document ingestion (PDF, DOCX, TXT)
- Intelligent text chunking with overlap
- Dual embedding strategy (general + enhanced)
- Vector similarity search using pgvector
- Multi-provider LLM support (OpenAI, AWS Bedrock)
- Three response modes: without context, with context, with guardrails
- Real-time document management
- Conversation tracking

### Architecture Pattern
The system follows a **RAG (Retrieval-Augmented Generation)** pattern:
1. Documents are processed and stored as vector embeddings
2. User queries are converted to embeddings
3. Similar document chunks are retrieved via vector search
4. Retrieved context is provided to LLM for response generation

---

## Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Web UI                        │
│  (streamlit_app.py)                                         │
│  - Document Upload Interface                                │
│  - Chat Interface                                           │
│  - Model Configuration                                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ├──────────────────┬──────────────────┬───────────────
                 │                  │                  │
        ┌────────▼────────┐ ┌──────▼──────┐  ┌───────▼────────┐
        │ Document Utils  │ │ Embeddings  │  │   Response     │
        │ (document_      │ │   Utils     │  │  Generation    │
        │  utils.py)      │ │ (embeddings_│  │ (response_     │
        │                 │ │  utils.py)  │  │  generation.py)│
        │ - PDF Extract   │ │ - OpenAI    │  │ - OpenAI Chat  │
        │ - DOCX Extract  │ │   Embed     │  │ - Bedrock      │
        │ - Text Clean    │ │ - Batch     │  │   Invoke       │
        │ - Chunking      │ │   Process   │  │ - 3 Modes      │
        └─────────────────┘ └─────────────┘  └────────────────┘
                 │                  │                  │
                 └──────────────────┴──────────────────┘
                                    │
                    ┌───────────────▼────────────────┐
                    │   PostgreSQL + pgvector        │
                    │                                │
                    │  Tables:                       │
                    │  - company_documents           │
                    │  - document_chunks             │
                    │  - conversations               │
                    │                                │
                    │  Indexes:                      │
                    │  - HNSW vector index           │
                    │  - B-tree metadata indexes     │
                    └────────────────────────────────┘
```

---

## Data Flow

### Document Upload Flow
```
1. User uploads document (PDF/DOCX/TXT)
   ↓
2. Extract text using format-specific parser
   ↓
3. Clean and normalize text
   ↓
4. Split into overlapping chunks (1000 chars, 200 overlap)
   ↓
5. Prefix each chunk with product metadata
   ↓
6. Generate embeddings in batches (128 chunks/batch)
   ↓
7. Store document metadata + chunks + embeddings in PostgreSQL
   ↓
8. Create vector indexes for fast similarity search
```

### Query Processing Flow
```
1. User submits question
   ↓
2. Generate query embedding using OpenAI
   ↓
3. Perform vector similarity search (pgvector <-> operator)
   ↓
4. Filter results by minimum similarity threshold
   ↓
5. Retrieve top-k most similar chunks
   ↓
6. Format context from retrieved chunks
   ↓
7. Generate response using selected LLM provider
   ↓
8. Display response with metadata (time, sources)
```

---

## Technology Stack

### Frontend
- **Streamlit 1.10+**: Web UI framework
  - Multi-tab interface
  - File upload handling
  - Real-time progress indicators
  - Session state management

### Backend Processing
- **Python 3.9+**: Core language
- **pdfplumber 0.7.4+**: PDF text extraction
- **python-docx 0.8.11+**: DOCX parsing
- **psycopg2-binary 2.9+**: PostgreSQL driver

### AI/ML Services
- **OpenAI API 1.0+**: 
  - Embeddings: `text-embedding-3-small` (1536 dimensions)
  - Chat: `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`
- **AWS Bedrock (boto3 1.26+)**:
  - Claude models: `claude-3.5-sonnet`, `claude-3-haiku`
  - Titan models: `amazon.titan-text-001`

### Database
- **PostgreSQL 12+**: Primary data store
- **pgvector 0.5.2+**: Vector similarity extension
  - HNSW indexing for fast approximate nearest neighbor search
  - Cosine similarity metric
  - 1536-dimensional vectors

### Configuration
- **python-dotenv 0.21+**: Environment variable management

---

## Database Schema

### Table: `company_documents`
Stores document metadata.

```sql
CREATE TABLE company_documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(50),              -- pdf, docx, txt
    file_path TEXT,
    total_chunks INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB                      -- flexible metadata storage
);
```

### Table: `document_chunks`
Stores text chunks with vector embeddings.

```sql
CREATE TABLE document_chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES company_documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    filename VARCHAR(255),
    product_name VARCHAR(100),
    content TEXT NOT NULL,
    content_length INTEGER,
    embedding vector(1536),             -- pgvector type
    chunk_metadata JSONB,
    embedding_type VARCHAR(20) DEFAULT 'general',  -- 'general' or 'enhanced'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

-- HNSW index for fast vector similarity search
CREATE INDEX idx_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);

-- B-tree indexes for metadata filtering
CREATE INDEX idx_document_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_product_name ON document_chunks(product_name);
CREATE INDEX idx_document_chunks_filename ON document_chunks(filename);
```

### Table: `conversations`
Tracks user interactions for analytics.

```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL,
    user_question TEXT NOT NULL,
    bot_response TEXT,
    chunks_used INTEGER[],              -- array of chunk IDs used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_conversations_session_id ON conversations(session_id);
```

---

## Core Modules

### 1. Document Processing (`document_utils.py`)

#### Text Extraction Functions
- `extract_text_from_pdf(file_bytes, filename)`: Uses pdfplumber for multi-page PDF parsing
- `extract_text_from_docx(file_bytes)`: Extracts from paragraphs and tables
- `extract_text_from_txt(file_bytes)`: UTF-8 with latin-1 fallback

#### Text Cleaning
```python
clean_extracted_text(text):
    - Normalize line endings
    - Collapse multiple spaces/tabs
    - Remove spaces before punctuation
    - Limit consecutive newlines to 2
    - Strip whitespace
```

#### Intelligent Chunking
```python
chunk_text(text, chunk_size=1000, overlap=200):
    Algorithm:
    1. Target chunk_size characters per chunk
    2. Prefer breaking at sentence boundaries ('. ' or '\n')
    3. Look for boundaries after 50% of chunk_size
    4. Overlap consecutive chunks by 'overlap' characters
    5. Return list of dicts: {content, start_pos, end_pos}
```

**Chunking Strategy Benefits:**
- Preserves semantic coherence by breaking at sentences
- Overlap ensures context continuity across chunks
- Position tracking enables source attribution

### 2. Embeddings (`embeddings_utils.py`)

#### Core Functions
```python
create_embedding(text, client, model="text-embedding-3-small"):
    - Single text → 1536-dim vector
    - Retry logic with exponential backoff
    - Error handling for API failures

create_embeddings_batch(texts, client, model):
    - Batch processing for efficiency
    - Up to 3 retries with backoff
    - Progress logging
```

#### Enhanced Embeddings
```python
generate_enhanced_json(product_name, chunk_content, client):
    - Uses GPT-4o-mini to extract structured metadata
    - Dynamic JSON schema (only fields with data)
    - Fields: product_name, specifications, features, etc.
    - Returns JSON string for embedding

generate_enhanced_embeddings_for_all(client, progress_callback):
    - Processes all 'general' chunks
    - Generates enhanced JSON representation
    - Creates new embeddings for enhanced content
    - Inserts as separate rows with embedding_type='enhanced'
```

**Dual Embedding Strategy:**
- **General embeddings**: Direct chunk content
- **Enhanced embeddings**: Structured metadata extraction
  - Better for specific queries (specs, features)
  - Enables hybrid search strategies

### 3. Response Generation (`response_generation.py`)

#### Three Response Modes

**1. Without Context**
```python
generate_response_without_context(question, model, client, provider):
    - Direct LLM query without RAG
    - Baseline for comparison
    - Uses general knowledge only
```

**2. With Context**
```python
generate_response_with_context(question, context_chunks, model, client, provider):
    - Provides all retrieved chunks to LLM
    - Instructs to synthesize from ALL passages
    - Combines information across chunks
    - Temperature: 0.7 (balanced creativity)
```

**3. With Guardrail**
```python
generate_response_with_guardrail(question, context_chunks, model, client, provider):
    - Strict: answer ONLY from provided context
    - Prohibits external knowledge
    - Allows synthesis and inference from context
    - Temperature: 0.3 (focused, deterministic)
    - Prevents hallucination
```

#### Provider Abstraction
```python
Supports:
- OpenAI: chat.completions.create()
- AWS Bedrock: invoke_model() with JSON body

Unified interface:
- Same function signatures
- Provider-specific error handling
- Automatic retry logic
```

---

## Embedding Strategy

### Vector Representation
- **Model**: OpenAI `text-embedding-3-small`
- **Dimensions**: 1536
- **Metric**: Cosine similarity
- **Storage**: PostgreSQL pgvector extension

### Embedding Types

#### General Embeddings
```
Input: "Product: AMI Smart Meter\n\nThe AMI smart meter features..."
Process: Direct embedding of prefixed chunk content
Use case: General semantic search
```

#### Enhanced Embeddings
```
Input: Chunk content
Process: 
  1. LLM extracts structured metadata (JSON)
  2. Embed the JSON representation
Output: {
  "product_name": "AMI Smart Meter",
  "features": ["remote monitoring", "real-time data"],
  "specifications": {"voltage": "240V", "current": "100A"},
  "standards": ["IEC 62052-11"]
}
Use case: Precise attribute-based queries
```

### Batch Processing
- **Batch size**: 128 chunks
- **Rate limiting**: Exponential backoff on errors
- **Progress tracking**: Real-time UI updates
- **Error handling**: Continue on individual failures

---

## Vector Search Implementation

### pgvector Configuration

#### Index Type: HNSW (Hierarchical Navigable Small World)
```sql
CREATE INDEX idx_document_chunks_embedding_hnsw
ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 200);
```

**Parameters:**
- `m = 16`: Max connections per layer (higher = better recall, more memory)
- `ef_construction = 200`: Build-time search depth (higher = better quality, slower build)

**Fallback: IVFFlat**
```sql
CREATE INDEX idx_document_chunks_embedding_ivfflat
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Search Query
```sql
SELECT id, document_id, content, metadata, 
       embedding <-> %s::vector AS distance
FROM document_chunks
WHERE embedding_type = %s
ORDER BY embedding <-> %s::vector
LIMIT %s
```

**Operator**: `<->` (L2 distance for cosine similarity)

### Similarity Scoring
```python
# Convert distance to similarity score
similarity = 1.0 / (1.0 + distance)

# Filter by threshold
filtered_chunks = [c for c in chunks if c['similarity'] >= min_similarity]
```

### Search Parameters
- **top_k**: Number of results (default: 5, range: 1-10)
- **min_similarity**: Threshold filter (default: 0.4, range: 0.0-1.0)
- **embedding_type**: 'general' or 'enhanced'

---

## Response Generation Pipeline

### Context Formatting
```python
def _build_context_block(context_chunks):
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(f"[Context {i}]\n{chunk['content']}")
    return "\n\n".join(parts)
```

### Prompt Templates

#### With Context Template
```
You are provided with {N} context passages. Read ALL of them carefully 
and synthesize information to answer comprehensively.

IMPORTANT: Use information from ALL context passages, not just one. 
Combine and synthesize.

[Context 1]
{content}

[Context 2]
{content}

...

Question: {question}

Instructions:
- Read and analyze ALL {N} passages
- Combine information from multiple passages
- Provide comprehensive answer
- Extract specific details (counts, lists, etc.)

Answer:
```

#### Guardrail Template
```
You are provided with {N} context passages. Answer based ONLY on this information.

STRICT RULES:
1. Read ALL {N} passages
2. Answer ONLY using information in contexts
3. You MAY synthesize and infer from passages
4. You MAY count, list, enumerate items mentioned
5. If contexts have relevant info, use it (can be partial)
6. ONLY say 'I don't have information' if NO relevant info at all
7. Do NOT use external knowledge

[Context passages...]

Question: {question}

Answer:
```

### Performance Metrics
- **Search time**: Vector similarity query duration
- **Response time**: LLM generation duration
- **Total time**: Search + response time
- Displayed in UI for transparency

---

## Security & Configuration

### Environment Variables
```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag_db
DB_USER=admin
DB_PASSWORD=secure_password

# AWS Bedrock (optional)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1

# Application
RAG_CHUNK_SIZE=1000
RAG_CHUNK_OVERLAP=200
```

### Security Best Practices
1. **Credentials**: Never commit `.env` to version control
2. **File permissions**: `chmod 600 .env`
3. **Database**: Strong passwords, restricted network access
4. **API keys**: Rotate regularly, use least-privilege
5. **HTTPS**: Use reverse proxy (nginx) for production
6. **Rate limiting**: Implement for public-facing deployments

### Caching Strategy
```python
@st.cache_resource
def get_openai_client(api_key):
    return OpenAI(api_key=api_key)

@st.cache_resource
def get_db_conn():
    return psycopg2.connect(...)
```

**Benefits:**
- Reuse connections across requests
- Reduce initialization overhead
- Improve response times

---

## Performance Considerations

### Database Optimization
- **HNSW index**: Fast approximate nearest neighbor (ANN) search
- **B-tree indexes**: Quick metadata filtering
- **Connection pooling**: Reuse database connections
- **Batch operations**: Minimize round trips

### Embedding Generation
- **Batch size**: 128 chunks (balance speed vs. memory)
- **Parallel processing**: Future enhancement opportunity
- **Caching**: Store embeddings, don't regenerate

### LLM Optimization
- **Context window**: Limit to top-k chunks (avoid token limits)
- **Temperature tuning**: Lower for factual, higher for creative
- **Model selection**: Balance cost, speed, quality

### Scalability
- **Horizontal**: Multiple Streamlit instances behind load balancer
- **Vertical**: Increase PostgreSQL resources for larger datasets
- **Caching**: Redis for frequently accessed chunks
- **CDN**: Static assets and document storage

---

## Monitoring & Observability

### Metrics to Track
- Document upload success rate
- Embedding generation time
- Search latency (p50, p95, p99)
- LLM response time
- Error rates by component
- Database query performance

### Logging
```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Log key events
logger.info(f"Document uploaded: {filename}, chunks: {len(chunks)}")
logger.error(f"Embedding generation failed: {error}")
```

### Health Checks
- Database connectivity
- OpenAI API availability
- Bedrock endpoint status
- Disk space for logs
- Memory usage

---

## Future Enhancements

### Technical Improvements
1. **Hybrid search**: Combine vector + keyword (BM25)
2. **Reranking**: Use cross-encoder for better relevance
3. **Streaming responses**: Real-time LLM output
4. **Multi-modal**: Support images, tables, charts
5. **Fine-tuning**: Custom embeddings for domain
6. **Query expansion**: Improve recall with synonyms

### Feature Additions
1. **User authentication**: Multi-tenant support
2. **Document versioning**: Track changes over time
3. **Analytics dashboard**: Usage patterns, popular queries
4. **Feedback loop**: User ratings to improve results
5. **Export functionality**: Download conversations
6. **API endpoints**: REST API for integration

---

## Conclusion

This RAG chatbot architecture provides a robust, scalable foundation for knowledge base applications. The modular design enables easy extension and customization while maintaining production-grade reliability and performance.

Key strengths:
- Dual embedding strategy for versatile search
- Multi-provider LLM support for flexibility
- Intelligent chunking preserves context
- Vector search with pgvector for speed
- Three response modes for different use cases
- Comprehensive error handling and retry logic

The system is production-ready with proper security, monitoring, and deployment automation.
