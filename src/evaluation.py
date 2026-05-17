"""
RAG System Evaluation
Important for showing academic rigor in your project!
"""

import os
import json
from datetime import datetime
from typing import List, Dict


class RAGEvaluator:
    """Evaluate RAG system performance"""
    
    def __init__(self, pipeline):
        self.pipeline = pipeline
        self.results = []
    
    def evaluate_retrieval(self, query: str, expected_keywords: List[str]) -> Dict:
        """Test if retrieval finds relevant content"""
        query_embedding = self.pipeline.embeddings.get_query_embedding(query)
        results = self.pipeline.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=5
        )
        
        retrieved_text = " ".join(results["documents"][0]).lower()
        
        found = sum(1 for kw in expected_keywords if kw.lower() in retrieved_text)
        recall = found / len(expected_keywords) if expected_keywords else 0
        
        return {
            "query": query,
            "recall": recall,
            "found_keywords": found,
            "total_keywords": len(expected_keywords)
        }
    
    def run_test_suite(self, test_cases: List[Dict]) -> Dict:
        """Run complete evaluation"""
        results = []
        
        for test in test_cases:
            # Test retrieval
            retrieval_score = self.evaluate_retrieval(
                test["question"],
                test.get("expected_keywords", [])
            )
            
            # Test full pipeline
            response = self.pipeline.query(test["question"])
            
            results.append({
                "question": test["question"],
                "retrieval_recall": retrieval_score["recall"],
                "response_length": len(response["answer"]),
                "sources_found": len(response["sources"]),
                "timestamp": datetime.now().isoformat()
            })
        
        # Calculate averages
        avg_recall = sum(r["retrieval_recall"] for r in results) / len(results)
        
        summary = {
            "total_tests": len(results),
            "average_recall": round(avg_recall, 3),
            "results": results
        }
        
        # Save
        os.makedirs("evaluation", exist_ok=True)
        with open("evaluation/eval_results.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        return summary


if __name__ == "__main__":
    from src.rag_pipeline import RAGPipeline
    
    pipeline = RAGPipeline()
    evaluator = RAGEvaluator(pipeline)
    
    test_cases = [
        {
            "question": "What is RAG?",
            "expected_keywords": ["retrieval", "generation", "augmented"]
        },
    ]
    
    results = evaluator.run_test_suite(test_cases)
    print(json.dumps(results, indent=2))