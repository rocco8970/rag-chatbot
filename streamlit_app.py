"""
RAG Chatbot - Streamlit UI
Final Year Project - Jamia Hamdard
"""

import streamlit as st
import os
import tempfile
import chromadb
from datetime import datetime
import uuid

from src.document_utils import DocumentProcessor, TextChunker
from src.embeddings_utils import EmbeddingsManager
from src.response_generation import ResponseGenerator

# ============= PAGE CONFIG =============
st.set_page_config(
    page_title="RAG Chatbot | Jamia Hamdard",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============= CUSTOM CSS =============
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #60a5fa, #a78bfa, #f472b6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        padding-top: 1rem;
    }
    
    .subtitle {
        text-align: center;
        color: #94a3b8;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    
    .stat-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        border-radius: 16px;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .stat-card:hover {
        background: rgba(255, 255, 255, 0.08);
        transform: translateY(-2px);
        border: 1px solid rgba(96, 165, 250, 0.5);
    }
    
    .stat-number {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .stat-label {
        color: #94a3b8;
        font-size: 0.85rem;
        margin-top: 0.5rem;
    }
    
    .user-message {
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        color: white;
        padding: 1rem 1.25rem;
        border-radius: 16px 16px 4px 16px;
        margin: 0.5rem 0;
        max-width: 75%;
        margin-left: auto;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        word-wrap: break-word;
    }
    
    .bot-message {
        background: rgba(255, 255, 255, 0.08);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        color: #e2e8f0;
        padding: 1rem 1.25rem;
        border-radius: 16px 16px 16px 4px;
        margin: 0.5rem 0;
        max-width: 75%;
        word-wrap: break-word;
    }
    
    .stButton > button {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        color: white;
        border: none;
        padding: 0.5rem 1.5rem;
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.4);
    }
    
    [data-testid="stSidebar"] {
        background: rgba(15, 12, 41, 0.9);
        backdrop-filter: blur(10px);
    }
    
    .badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    
    .badge-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
    .badge-purple { background: rgba(139, 92, 246, 0.2); color: #a78bfa; }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .badge-pink { background: rgba(236, 72, 153, 0.2); color: #f472b6; }
    .badge-yellow { background: rgba(245, 158, 11, 0.2); color: #fbbf24; }
    
    .source-box {
        background: rgba(59, 130, 246, 0.1);
        border-left: 3px solid #3b82f6;
        padding: 0.75rem;
        border-radius: 8px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
        color: #cbd5e1;
    }
    
    .welcome-box {
        text-align: center;
        padding: 3rem;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "documents" not in st.session_state:
        st.session_state.documents = []
    if "chroma_client" not in st.session_state:
        st.session_state.chroma_client = chromadb.PersistentClient(path="./chroma_db")
        st.session_state.collection = st.session_state.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
    if "embeddings_manager" not in st.session_state:
        with st.spinner("⏳ Loading AI models... (first time only, ~1 minute)"):
            st.session_state.embeddings_manager = EmbeddingsManager()
    if "total_queries" not in st.session_state:
        st.session_state.total_queries = 0


init_session_state()


st.markdown('<h1 class="main-title">🤖 RAG Chatbot</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="subtitle">Intelligent Document Q&A System • Final Year Project • Jamia Hamdard</p>', 
    unsafe_allow_html=True
)


with st.sidebar:
    st.markdown("### 📚 Document Manager")
    
    # Model Selection
    provider = st.selectbox(
        "🧠 Select AI Model",
        ["gemini", "groq"],
        format_func=lambda x: {
            "gemini": "⚡ Google Gemini 2.0 Flash",
            "groq": "🚀 Groq Llama 3.1 (Super Fast)"
        }[x]
    )
    
    st.markdown(f"""
    <div style='background: rgba(96, 165, 250, 0.1); padding: 0.75rem; 
                border-radius: 8px; border: 1px solid rgba(96, 165, 250, 0.3);
                margin-bottom: 1rem;'>
        <strong style='color: #60a5fa;'>🧠 Active Model:</strong>
        <span style='color: #e2e8f0;'> {provider.upper()}</span><br>
        <small style='color: #94a3b8;'>Free • Fast • Powerful</small>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 📤 Upload Documents")
    uploaded_files = st.file_uploader(
        "Drag and drop files here",
        type=["pdf", "txt", "docx", "md", "csv"],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files and st.button("🔄 Process Documents"):
        processor = DocumentProcessor()
        chunker = TextChunker(chunk_size=500, chunk_overlap=50)
        
        progress = st.progress(0)
        status = st.empty()
        
        for idx, uploaded_file in enumerate(uploaded_files):
            status.text(f"Processing {uploaded_file.name}...")
            
            with tempfile.NamedTemporaryFile(
                delete=False, 
                suffix=os.path.splitext(uploaded_file.name)[1]
            ) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name
            
            try:
                text, metadata = processor.process_file(tmp_path)
                chunks = chunker.chunk_text(text)
                
                embeddings = st.session_state.embeddings_manager.get_embeddings(chunks)
                
                ids = [str(uuid.uuid4()) for _ in chunks]
                metadatas = [
                    {
                        "source": uploaded_file.name,
                        "chunk_index": i,
                        "uploaded_at": datetime.now().isoformat()
                    }
                    for i in range(len(chunks))
                ]
                
                st.session_state.collection.add(
                    documents=chunks,
                    embeddings=embeddings.tolist(),
                    metadatas=metadatas,
                    ids=ids
                )
                
                st.session_state.documents.append({
                    "name": uploaded_file.name,
                    "chunks": len(chunks),
                    "format": metadata.get("format", "unknown")
                })
                
                os.unlink(tmp_path)
                progress.progress((idx + 1) / len(uploaded_files))
                
            except Exception as e:
                st.error(f"Error: {e}")
                os.unlink(tmp_path)
        
        status.text("✅ All documents processed!")
        st.success(f"✅ Processed {len(uploaded_files)} document(s)")
        st.rerun()
    
    st.markdown("---")
    
    if st.session_state.documents:
        st.markdown("### 📂 Loaded Documents")
        for doc in st.session_state.documents:
            display_name = doc['name'][:25] + '...' if len(doc['name']) > 25 else doc['name']
            st.markdown(f"""
            <div style='background: rgba(255,255,255,0.05); padding: 0.5rem; 
                        border-radius: 8px; margin: 0.3rem 0;
                        border-left: 3px solid #60a5fa;'>
                <strong style='color: #e2e8f0;'>📄 {display_name}</strong><br>
                <small style='color: #94a3b8;'>
                    {doc['chunks']} chunks • {doc['format'].upper()}
                </small>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    st.markdown("### ⚙️ Settings")
    top_k = st.slider("Context chunks", 1, 10, 5, help="How many chunks to retrieve")
    
    st.markdown("---")
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🗑️ Clear All Documents"):
        try:
            st.session_state.chroma_client.delete_collection("documents")
        except:
            pass
        st.session_state.collection = st.session_state.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"}
        )
        st.session_state.documents = []
        st.session_state.messages = []
        st.success("✅ All cleared!")
        st.rerun()
    
    st.markdown("---")
    
    st.markdown("### 👨‍🎓 Project Info")
    st.markdown("""
    <div style='background: rgba(255,255,255,0.05); padding: 1rem; 
                border-radius: 12px; border: 1px solid rgba(255,255,255,0.1);'>
        <strong style='color: #60a5fa;'>Student:</strong> 
        <span style='color: #e2e8f0;'>Your Name</span><br>
        <strong style='color: #60a5fa;'>University:</strong> 
        <span style='color: #e2e8f0;'>Jamia Hamdard</span><br>
        <strong style='color: #60a5fa;'>Department:</strong> 
        <span style='color: #e2e8f0;'>Computer Science</span><br>
        <strong style='color: #60a5fa;'>Year:</strong> 
        <span style='color: #e2e8f0;'>2024-25</span>
    </div>
    """, unsafe_allow_html=True)


col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{len(st.session_state.documents)}</div>
        <div class="stat-label">📄 Documents</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    total_chunks = sum(d["chunks"] for d in st.session_state.documents)
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{total_chunks}</div>
        <div class="stat-label">🧩 Total Chunks</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{st.session_state.total_queries}</div>
        <div class="stat-label">💬 Questions</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="stat-card">
        <div class="stat-number">{provider.upper()}</div>
        <div class="stat-label">🤖 AI Model</div>
    </div>
    """, unsafe_allow_html=True)


st.markdown("<br>", unsafe_allow_html=True)

st.markdown("""
<div style='text-align: center; margin: 1rem 0;'>
    <span class="badge badge-blue">Python</span>
    <span class="badge badge-purple">Streamlit</span>
    <span class="badge badge-green">ChromaDB</span>
    <span class="badge badge-pink">Sentence Transformers</span>
    <span class="badge badge-yellow">Gemini AI</span>
    <span class="badge badge-blue">Groq AI</span>
    <span class="badge badge-purple">RAG Pipeline</span>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

st.markdown("### 💬 Chat with Your Documents")

if not st.session_state.messages:
    st.markdown("""
    <div class="welcome-box">
        <h2 style='color: #60a5fa;'>👋 Welcome!</h2>
        <p style='color: #94a3b8; margin: 1rem 0;'>
            Upload documents from the sidebar and start asking questions.
        </p>
        <br>
        <p style='color: #e2e8f0; font-weight: 600;'>Try asking:</p>
        <div style='color: #94a3b8; line-height: 2;'>
            📌 "Summarize the main points"<br>
            📌 "What are the key concepts?"<br>
            📌 "Explain in simple terms"<br>
            📌 "What does the document say about [topic]?"
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.markdown(f"""
            <div style='display: flex; justify-content: flex-end; margin: 0.5rem 0;'>
                <div class="user-message">{message["content"]}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style='display: flex; justify-content: flex-start; margin: 0.5rem 0;'>
                <div class="bot-message">{message["content"]}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if "sources" in message and message["sources"]:
                with st.expander(f"📎 View {len(message['sources'])} sources"):
                    for i, source in enumerate(message["sources"]):
                        st.markdown(f"""
                        <div class="source-box">
                            <strong style='color: #60a5fa;'>Source {i+1}:</strong> 
                            {source.get('source', 'Unknown')}<br>
                            <small style='color: #94a3b8;'>
                                Chunk #{source.get('chunk_index', 'N/A')}
                            </small>
                        </div>
                        """, unsafe_allow_html=True)


if st.session_state.documents:
    user_input = st.chat_input("Ask anything about your documents...")
    
    if user_input:
        st.session_state.messages.append({
            "role": "user",
            "content": user_input
        })
        
        with st.spinner(f"🔍 Searching documents and generating answer with {provider.upper()}..."):
            try:
                query_embedding = st.session_state.embeddings_manager.get_query_embedding(user_input)
                
                results = st.session_state.collection.query(
                    query_embeddings=[query_embedding.tolist()],
                    n_results=top_k
                )
                
                context = "\n\n".join(results["documents"][0])
                sources = results["metadatas"][0]
                
                generator = ResponseGenerator(provider=provider)
                answer = generator.generate_response(user_input, context)
                
                st.session_state.messages.append({
                    "role": "bot",
                    "content": answer,
                    "sources": sources
                })
                
                st.session_state.total_queries += 1
                
            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.messages.append({
                    "role": "bot",
                    "content": f"Sorry, I encountered an error: {str(e)}",
                    "sources": []
                })
        
        st.rerun()
else:
    st.info("👈 Please upload documents from the sidebar to start chatting!")


st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("""
<div style='text-align: center; color: #64748b; padding: 1rem;
            border-top: 1px solid rgba(255,255,255,0.1); margin-top: 2rem;'>
    <p>Built with ❤️ for Final Year Project</p>
    <p style='font-size: 0.8rem;'>
        Jamia Hamdard • Department of Computer Science • 2024-25
    </p>
</div>
""", unsafe_allow_html=True)