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

\`\`\`bash
streamlit run streamlit_app.py
\`\`\`

Open http://localhost:8501 in your browser.

## 📁 Project Structure

\`\`\`
rag-chatbot/
├── src/
│   ├── document_utils.py      # Document processing
│   ├── embeddings_utils.py    # Free embeddings
│   ├── response_generation.py # LLM responses
│   ├── rag_pipeline.py        # Main pipeline
│   └── evaluation.py          # Evaluation metrics
├── scripts/
│   └── checking_db.py         # DB utilities
├── docs/
│   ├── DEPLOYMENT.md
│   ├── USER_GUIDE.md
│   └── TECHNICAL_ARCHITECTURE.md
├── data/
│   └── uploads/               # User uploads
├── chroma_db/                 # Vector database
├── streamlit_app.py           # Main app
├── requirements.txt
├── .env.example
└── README.md
\`\`\`

## 🛠️ Technology Stack

| Component | Technology |
|-----------|-----------|
| **Frontend** | Streamlit |
| **LLM** | Google Gemini / Groq |
| **Embeddings** | Sentence Transformers (Free) |
| **Vector DB** | ChromaDB |
| **Document Processing** | PyMuPDF, python-docx |
| **Language** | Python 3.9+ |

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