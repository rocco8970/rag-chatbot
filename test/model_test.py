import os
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"🔑 Using API Key: {api_key[:10]}...{api_key[-4:]}")

client = genai.Client(api_key=api_key)

print("\n📋 Available Models for your API Key:\n")
print("=" * 50)

for model in client.models.list():
    print(f"✅ {model.name}")

print("=" * 50)