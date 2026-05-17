"""
FastAPI Backend for RAG Chatbot
Connects React frontend with Python RAG pipeline
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb

# Add parent directory to path so we can import from src/
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.document_utils import DocumentProcessor, TextChunker
from src.embeddings_utils import EmbeddingsManager
from src.response_generation import ResponseGenerator


# ============= FASTAPI APP =============
app = FastAPI(
    title="RAG Chatbot API",
    description="Backend API for Intelligent Document Q&A System",
    version="1.0.0"
)

# Enable CORS so React can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= LAZY-LOADED COMPONENTS =============
_embeddings_manager = None
_chroma_client = None
_collection = None

# Store uploaded documents info
documents_db = []
chat_history = []


def get_embeddings_manager():
    """Lazy load embeddings manager"""
    global _embeddings_manager
    if _embeddings_manager is None:
        print("🚀 Loading embeddings model (first time)...")
        _embeddings_manager = EmbeddingsManager()
        print("✅ Embeddings ready!")
    return _embeddings_manager


def get_collection():
    """Lazy load ChromaDB collection"""
    global _chroma_client, _collection
    if _collection is None:
        print("🚀 Initializing ChromaDB...")
        _chroma_client = chromadb.PersistentClient(path="./chroma_db")
        _collection = _chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        print("✅ ChromaDB ready!")
    return _collection


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    print("\n" + "="*60)
    print("🚀 RAG Chatbot API Starting...")
    print("="*60)
    get_embeddings_manager()
    get_collection()
    print("✅ All systems ready!")
    print("📍 API: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    print("="*60 + "\n")


# ============= REQUEST/RESPONSE MODELS =============
class ChatRequest(BaseModel):
    question: str
    model: str = "gemini"
    top_k: int = 5


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence_scores: Optional[List[float]] = []
    model_used: str
    timestamp: str


class DocumentInfo(BaseModel):
    id: str
    name: str
    chunks: int
    format: str
    uploaded_at: str


class StatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_queries: int
    available_models: List[str]


# ============= API ENDPOINTS =============

@app.get("/")
def root():
    return {
        "message": "🤖 RAG Chatbot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "embeddings": "ready" if _embeddings_manager else "not loaded",
            "vector_db": "ready" if _collection else "not loaded",
            "llm": "ready"
        }
    }


@app.get("/api/stats", response_model=StatsResponse)
def get_stats():
    return StatsResponse(
        total_documents=len(documents_db),
        total_chunks=get_collection().count(),
        total_queries=len(chat_history),
        available_models=["gemini", "groq"]
    )


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    allowed_extensions = ['.pdf', '.txt', '.docx', '.md', '.csv']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {allowed_extensions}"
        )
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        processor = DocumentProcessor()
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        
        text, metadata = processor.process_file(tmp_path)
        chunks = chunker.chunk_text(text)
        
        # Use lazy-loaded embeddings
        embeddings = get_embeddings_manager().get_embeddings(chunks)
        
        doc_id = str(uuid.uuid4())
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "source": file.filename,
                "chunk_index": i,
                "uploaded_at": datetime.now().isoformat()
            }
            for i in range(len(chunks))
        ]
        
        get_collection().add(
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids
        )
        
        doc_info = {
            "id": doc_id,
            "name": file.filename,
            "chunks": len(chunks),
            "format": metadata.get("format", "unknown"),
            "uploaded_at": datetime.now().isoformat()
        }
        documents_db.append(doc_info)
        
        os.unlink(tmp_path)
        
        return {
            "status": "success",
            "message": f"Successfully processed {file.filename}",
            "document": doc_info
        }
        
    except Exception as e:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents", response_model=List[DocumentInfo])
def list_documents():
    return documents_db


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    global documents_db
    
    doc = next((d for d in documents_db if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        results = get_collection().get(where={"doc_id": doc_id})
        if results["ids"]:
            get_collection().delete(ids=results["ids"])
    except Exception as e:
        print(f"Warning: {e}")
    
    documents_db = [d for d in documents_db if d["id"] != doc_id]
    
    return {"status": "success", "message": f"Deleted {doc['name']}"}


@app.delete("/api/documents")
def clear_all_documents():
    global documents_db, chat_history, _collection, _chroma_client
    
    try:
        _chroma_client.delete_collection("documents")
    except:
        pass
    
    _collection = _chroma_client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"}
    )
    
    documents_db = []
    chat_history = []
    
    return {"status": "success", "message": "All data cleared"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    if len(documents_db) == 0:
        raise HTTPException(
            status_code=400,
            detail="Please upload documents first"
        )
    
    try:
        query_embedding = get_embeddings_manager().get_query_embedding(request.question)
        
        results = get_collection().query(
            query_embeddings=[query_embedding.tolist()],
            n_results=request.top_k
        )
        
        context = "\n\n".join(results["documents"][0])
        sources = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]
        
        generator = ResponseGenerator(provider=request.model)
        answer = generator.generate_response(request.question, context)
        
        chat_entry = {
            "question": request.question,
            "answer": answer,
            "model": request.model,
            "timestamp": datetime.now().isoformat()
        }
        chat_history.append(chat_entry)
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            confidence_scores=[float(d) for d in distances],
            model_used=request.model,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/chat/history")
def get_chat_history():
    return {
        "total": len(chat_history),
        "history": chat_history
    }


@app.delete("/api/chat/history")
def clear_chat_history():
    global chat_history
    chat_history = []
    return {"status": "success", "message": "Chat history cleared"}


# ============= RUN SERVER =============
if __name__ == "__main__":
    import uvicorn
    
    # IMPORTANT: reload=False to avoid multiprocessing issues!
    uvicorn.run(
        app,  # Pass app object directly (not "main:app")
        host="0.0.0.0",
        port=8000,
        reload=False  # Disabled to fix multiprocessing error
    )