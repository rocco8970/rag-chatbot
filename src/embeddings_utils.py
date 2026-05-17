
"""
Free Embeddings using Sentence Transformers
No API key required - runs locally!
"""

from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingsManager:
    """Manages text embeddings using free local models"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embeddings model
        
        Args:
            model_name: HuggingFace model name (default is free & fast)
        """
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        logger.info("✅ Embedding model loaded successfully")
    
    def get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of text strings
            
        Returns:
            numpy array of embeddings
        """
        if not texts:
            return np.array([])
        
        embeddings = self.model.encode(
            texts, 
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings
    
    def get_query_embedding(self, query: str) -> np.ndarray:
        """
        Generate embedding for a single query
        
        Args:
            query: Question text
            
        Returns:
            numpy array of embedding
        """
        return self.model.encode([query], convert_to_numpy=True)[0]
    
    def get_embedding_dimension(self) -> int:
        """Returns the dimension of embeddings"""
        return self.model.get_sentence_embedding_dimension()


# Backward compatibility - if your old code uses these function names
def create_embeddings(texts):
    """Helper function for backward compatibility"""
    manager = EmbeddingsManager()
    return manager.get_embeddings(texts)


def embed_query(query):
    """Helper function for backward compatibility"""
    manager = EmbeddingsManager()
    return manager.get_query_embedding(query)


if __name__ == "__main__":
    # Test the embeddings
    print("Testing embeddings...")
    em = EmbeddingsManager()
    
    test_texts = [
        "Hello, this is a test sentence.",
        "RAG stands for Retrieval Augmented Generation."
    ]
    
    embeddings = em.get_embeddings(test_texts)
    print(f"✅ Created {len(embeddings)} embeddings")
    print(f"✅ Dimension: {em.get_embedding_dimension()}")
    print(f"✅ Shape: {embeddings.shape}")