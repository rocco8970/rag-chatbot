"""
Main RAG Pipeline
Orchestrates document processing, embedding, and response generation
"""

import os
import uuid
from datetime import datetime
from typing import Dict, List
import chromadb

from src.document_utils import DocumentProcessor, TextChunker
from src.embeddings_utils import EmbeddingsManager
from src.response_generation import ResponseGenerator


class RAGPipeline:
    """Complete RAG pipeline"""
    
    def __init__(self, llm_provider: str = "gemini"):
        self.processor = DocumentProcessor()
        self.chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        self.embeddings = EmbeddingsManager()
        self.generator = ResponseGenerator(provider=llm_provider)
        
        # Vector DB
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.chat_history = []
    
    def ingest_document(self, file_path: str) -> Dict:
        """Process and store a document"""
        # Extract text
        text, metadata = self.processor.process_file(file_path)
        
        # Chunk
        chunks = self.chunker.chunk_text(text)
        
        # Generate embeddings
        embeddings = self.embeddings.get_embeddings(chunks)
        
        # Store
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "source": metadata["source"],
                "chunk_index": i,
                "ingested_at": datetime.now().isoformat()
            }
            for i in range(len(chunks))
        ]
        
        self.collection.add(
            documents=chunks,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=ids
        )
        
        return {
            "status": "success",
            "filename": metadata["source"],
            "chunks_created": len(chunks)
        }
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """Ask a question"""
        # Embed query
        query_embedding = self.embeddings.get_query_embedding(question)
        
        # Retrieve
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k
        )
        
        # Build context
        context = "\n\n".join(results["documents"][0])
        sources = results["metadatas"][0]
        distances = results.get("distances", [[]])[0]
        
        # Generate response
        answer = self.generator.generate_response(question, context)
        
        # Save history
        self.chat_history.append({
            "question": question,
            "answer": answer,
            "sources": sources,
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence_scores": distances,
            "context_preview": context[:300] + "..."
        }
    
    def get_stats(self) -> Dict:
        """Get system statistics"""
        return {
            "total_chunks": self.collection.count(),
            "total_queries": len(self.chat_history),
            "history": self.chat_history
        }
    
    def clear_all(self):
        """Clear everything"""
        self.client.delete_collection("documents")
        self.collection = self.client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        self.chat_history = []