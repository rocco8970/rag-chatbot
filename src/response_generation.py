"""
Response Generation using FREE LLMs
Supports: Google Gemini & Groq (Llama)
"""

import os
from dotenv import load_dotenv
from google import genai
from groq import Groq

# Load environment variables from .env
load_dotenv()


class ResponseGenerator:
    """Generates responses using free LLM APIs"""
    
    def __init__(self, provider: str = None):
        """
        Initialize the response generator
        
        Args:
            provider: 'gemini' or 'groq' (defaults to env variable)
        """
        self.provider = provider or os.getenv("LLM_PROVIDER", "gemini")
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the selected LLM"""
        if self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "groq":
            self._init_groq()
        else:
            raise ValueError(f"❌ Unknown provider: {self.provider}")
    
    def _init_gemini(self):
        """Initialize Google Gemini"""
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key:
            raise ValueError(
                "❌ GEMINI_API_KEY not found in .env file!\n"
                "Get free key from: https://makersuite.google.com/app/apikey"
            )
        
        self.client = genai.Client(api_key=api_key)
        self.model_name = "gemini-2.5-flash"  # ✅ UPDATED - Latest Gemini model
        print(f"✅ Gemini AI ready! (Model: {self.model_name})")
    
    def _init_groq(self):
        """Initialize Groq"""
        api_key = os.getenv("GROQ_API_KEY")
        
        if not api_key:
            raise ValueError(
                "❌ GROQ_API_KEY not found in .env file!\n"
                "Get free key from: https://console.groq.com/keys"
            )
        
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.1-8b-instant"
        print(f"✅ Groq AI ready! (Model: {self.model_name})")
    
    def generate_response(self, question: str, context: str) -> str:
        """Generate a response based on question and context"""
        prompt = self._build_prompt(question, context)
        
        try:
            if self.provider == "gemini":
                return self._generate_gemini(prompt)
            elif self.provider == "groq":
                return self._generate_groq(prompt)
        except Exception as e:
            return f"❌ Error: {str(e)}"
    
    def _generate_gemini(self, prompt: str) -> str:
        """Generate response using Gemini with fallback models"""
        # ✅ UPDATED - Using NEW Gemini models that work with your API key
        candidates = [
            self.model_name,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
            "gemini-flash-latest",
            "gemini-pro-latest",
        ]
        
        last_err = None
        tried_models = []
        
        for model in candidates:
            if model in tried_models:
                continue
            tried_models.append(model)
            
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                self.model_name = model  # Save working model
                return response.text
            except Exception as e:
                last_err = e
                continue
        
        return f"❌ All Gemini models failed. Last error: {last_err}"
    
    def _generate_groq(self, prompt: str) -> str:
        """Generate response using Groq"""
        completion = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that answers questions based on provided context."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model=self.model_name,
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content
    
    def stream_response(self, question: str, context: str):
        """Stream response tokens as a generator — used by FastAPI WebSocket."""
        prompt = self._build_prompt(question, context)
        if self.provider == "gemini":
            yield from self._stream_gemini(prompt)
        elif self.provider == "groq":
            yield from self._stream_groq(prompt)

    def _stream_gemini(self, prompt: str):
        """Yield text chunks from Gemini streaming API."""
        candidates = [
            self.model_name,
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
        ]
        tried = []
        for model in candidates:
            if model in tried:
                continue
            tried.append(model)
            try:
                for chunk in self.client.models.generate_content_stream(
                    model=model, contents=prompt
                ):
                    if chunk.text:
                        yield chunk.text
                self.model_name = model
                return
            except Exception:
                continue
        yield "❌ All Gemini models failed during streaming."

    def _stream_groq(self, prompt: str):
        """Yield text chunks from Groq streaming API."""
        stream = self.client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant that answers questions based on provided context.",
                },
                {"role": "user", "content": prompt},
            ],
            model=self.model_name,
            temperature=0.7,
            max_tokens=1024,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def _build_prompt(self, question: str, context: str) -> str:
        """Build the prompt for the LLM"""
        return f"""You are a helpful AI assistant. Answer the question based ONLY on the context provided below.
If the answer is not in the context, say "I don't have enough information to answer this question."

CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Provide a clear, concise answer
- Use bullet points if listing multiple items
- Cite specific information from the context
- Be helpful and friendly

ANSWER:"""


# Quick test
if __name__ == "__main__":
    print("\n🧪 Testing Response Generators...\n")
    
    test_context = """
    RAG (Retrieval-Augmented Generation) is a technique that combines 
    information retrieval with text generation. It first retrieves relevant 
    documents from a knowledge base, then uses them as context for an LLM 
    to generate accurate answers based on the retrieved information.
    """
    
    test_question = "What is RAG?"
    
    # Test Gemini
    print("=" * 60)
    print("TESTING GEMINI")
    print("=" * 60)
    try:
        gemini_gen = ResponseGenerator(provider="gemini")
        gemini_response = gemini_gen.generate_response(test_question, test_context)
        print(f"\n📝 Question: {test_question}")
        print(f"\n🤖 Gemini Response:\n{gemini_response}")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
    
    print("\n")
    
    # Test Groq
    print("=" * 60)
    print("TESTING GROQ")
    print("=" * 60)
    try:
        groq_gen = ResponseGenerator(provider="groq")
        groq_response = groq_gen.generate_response(test_question, test_context)
        print(f"\n📝 Question: {test_question}")
        print(f"\n🤖 Groq Response:\n{groq_response}")
    except Exception as e:
        print(f"❌ Groq Error: {e}")
    
    print("\n🎉 Tests completed!")