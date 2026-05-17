# 🤖 RAG Chatbot - Intelligent Document Q&A System

> **Final Year Project** • Jamia Hamdard • Department of Computer Science • 2024-25

A modern AI-powered chatbot that uses **Retrieval-Augmented Generation (RAG)** to answer questions from your documents with precise source attribution.

![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 🎯 Features

- 📄 **Multi-Format Support**: PDF, DOCX, TXT, MD, CSV
- 🧠 **Free AI Models**: Gemini, Groq (no paid APIs!)
- 🔍 **Smart Retrieval**: Semantic search with ChromaDB
- 💬 **Source Attribution**: Every answer includes sources
- 📊 **Real-time Analytics**: Track usage and performance
- 🎨 **Modern UI**: Glass morphism design
- ⚡ **Fast**: Sub-second response times

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- Free API key from [Google Gemini](https://makersuite.google.com/app/apikey) or [Groq](https://console.groq.com/keys)

### Installation

\`\`\`bash
# Clone repository
git clone https://github.com/rocco8970/rag-chatbot.git
cd rag-chatbot

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env and add your API key
\`\`\`

### Run the Application

#### Option A — Streamlit UI (original)
\`\`\`bash
streamlit run streamlit_app.py
\`\`\`
Open http://localhost:8501 in your browser.

#### Option B — React + FastAPI UI (new)
Requires the Python backend dependencies installed (`pip install -r requirements.txt`).

\`\`\`bash
# Terminal 1 — Python backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — React frontend
cd frontend
npm install   # first time only
npm run dev
\`\`\`
Open http://localhost:5173 in your browser.

## 📁 Project Structure

\`\`\`
rag-chatbot/
├── backend/
│   └── main.py                # FastAPI app (REST + WebSocket)
├── frontend/                  # React 18 + Vite UI
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── Sidebar.jsx
│           ├── ChatWindow.jsx
│           └── Message.jsx
├── src/
│   ├── document_utils.py      # Document processing
│   ├── embeddings_utils.py    # Free embeddings
│   ├── response_generation.py # LLM responses (+ streaming)
│   ├── rag_pipeline.py        # Main pipeline
│   └── evaluation.py          # Evaluation metrics
├── docs/
│   ├── DEPLOYMENT.md
│   ├── USER_GUIDE.md
│   └── TECHNICAL_ARCHITECTURE.md
├── chroma_db/                 # Vector database
├── streamlit_app.py           # Original Streamlit UI (still works)
├── requirements.txt
├── .env.example
└── README.md
\`\`\`

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend (Streamlit UI)** | Streamlit |
| **Frontend (React UI)** | React 18 + Vite + Tailwind CSS + Framer Motion |
| **Backend API** | FastAPI + WebSockets |
| **LLM** | Google Gemini 2.5 Flash / Groq Llama 3.1 (both free) |
| **Embeddings** | Sentence Transformers — `all-MiniLM-L6-v2` (local, free) |
| **Vector DB** | ChromaDB (persistent, cosine similarity) |
| **Document Processing** | PyMuPDF, python-docx, pandas |
| **Language** | Python 3.9+ / Node 18+ |

## 📊 System Architecture

\`\`\`
User Question
    ↓
[Embedding Model] → Query Vector
    ↓
[Vector Database] → Top-K Relevant Chunks
    ↓
[Context Builder] → Formatted Context
    ↓
[LLM (Gemini/Groq)] → Generated Answer
    ↓
Response with Sources
\`\`\`

## 🎓 Academic Information

- **Student:** Your Name
- **Roll No:** Your Roll Number
- **Supervisor:** Prof. Name
- **University:** Jamia Hamdard
- **Department:** Computer Science
- **Year:** 2024-25

## 📝 License

MIT License - Free for educational use

## 🙏 Acknowledgments

- Jamia Hamdard, Department of Computer Science
- Google Gemini API (Free tier)
- Open source community