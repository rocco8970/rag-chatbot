import os
import json
import time
import datetime
from pathlib import Path
import io
import re
from typing import Optional, Dict

import streamlit as st
import psycopg2
from openai import OpenAI
import boto3
from dotenv import load_dotenv

import pdfplumber
import docx

from response_generation import (
    generate_response_without_context,
    generate_response_with_context,
    generate_response_with_guardrail,
)


# -----------------------------
# Configuration
# -----------------------------
load_dotenv()

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# AWS Bedrock / AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# Database
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "admin")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# Chunking / Embedding settings
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIM = 1536


# -----------------------------
# Model configuration dictionaries
# -----------------------------
# OpenAI model identifiers (examples)
OPENAI_MODELS: Dict[str, str] = {
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "gpt-3.5-turbo": "gpt-3.5-turbo",
}

# AWS Bedrock model identifiers (these names may vary by Bedrock region/account)
BEDROCK_MODELS: Dict[str, str] = {
    "claude-3.5-sonnet-v2": "anthropic.claude-3.5-sonnet-v2",
    "claude-3.5-sonnet": "anthropic.claude-3.5-sonnet",
    "claude-3-haiku": "anthropic.claude-3-haiku",
    "claude-3-sonnet": "anthropic.claude-3-sonnet",
    "titan-text": "amazon.titan-text-001",
}


# -----------------------------
# Cached client factories
# -----------------------------

@st.cache_resource
def get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """Return a cached OpenAI client. Uses environment or provided api_key."""
    key = api_key or OPENAI_API_KEY
    if key:
        return OpenAI(api_key=key)
    # If no key provided, create default client which relies on env
    return OpenAI()


@st.cache_resource
def get_bedrock_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    region_name: Optional[str] = None,
):
    """Return a cached boto3 Bedrock client. If credentials are omitted, boto3
    will use the default credential chain (env, profile, role).
    """
    region = region_name or AWS_REGION
    kwargs = {"region_name": region}
    if aws_access_key_id and aws_secret_access_key:
        kwargs["aws_access_key_id"] = aws_access_key_id
        kwargs["aws_secret_access_key"] = aws_secret_access_key

    return boto3.client("bedrock-runtime", **kwargs)


# -----------------------------
# Page configuration
# -----------------------------
st.set_page_config(page_title="Demo Chatbot", page_icon="🤖", layout="wide")


# -----------------------------
# Initialize clients
# -----------------------------
openai_client = get_openai_client()
bedrock_client = None
try:
    bedrock_client = get_bedrock_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
except Exception:
    # If boto3 not configured or Bedrock not available, continue without client
    bedrock_client = None


# -----------------------------
# Database helpers
# -----------------------------
@st.cache_resource
def get_db_conn():
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = True
    return conn


def _pg_vector_literal(emb):
    # convert list of floats to Postgres vector literal string
    return "[" + ",".join(str(float(x)) for x in emb) + "]"


def store_document_and_chunks(conn, filename: str, file_type: str, file_path: str, chunks: list, embeddings: list, metadata: dict = None, embedding_type: str = "general"):
    """Insert document metadata and chunks into DB. Returns document_id.

    `chunks` is a list of dicts with keys: content, start_pos, end_pos
    `embeddings` is a list of vectors aligned with chunks
    """
    metadata = metadata or {}
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO company_documents (filename, file_type, file_path, total_chunks, metadata) VALUES (%s,%s,%s,%s,%s) RETURNING id;",
            (filename, file_type, file_path, len(chunks), json.dumps(metadata)),
        )
        doc_id = cur.fetchone()[0]

        insert_sql = """
        INSERT INTO document_chunks (document_id, chunk_index, filename, product_name, content, content_length, embedding, chunk_metadata, embedding_type)
        VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s);
        """

        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            content = chunk.get("content")
            chunk_meta = json.dumps({"start_pos": chunk.get("start_pos"), "end_pos": chunk.get("end_pos")})
            pg_vec = _pg_vector_literal(emb)
            product_name = metadata.get("product_name") if isinstance(metadata, dict) else None
            cur.execute(insert_sql, (doc_id, i, filename, product_name, content, len(content), pg_vec, chunk_meta, embedding_type))

    return doc_id


def get_all_documents(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT id, filename, total_chunks, uploaded_at, metadata FROM company_documents ORDER BY uploaded_at DESC;")
        rows = cur.fetchall()
    docs = []
    for r in rows:
        docs.append({"id": r[0], "filename": r[1], "total_chunks": r[2], "uploaded_at": r[3], "metadata": r[4]})
    return docs


def delete_document(conn, doc_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM company_documents WHERE id = %s;", (int(doc_id),))
    return True


# -----------------------------
# UI: Tabs
# -----------------------------
tab1, tab2 = st.tabs(["📚 Knowledge Base Upload", "💬 Chat"])

with tab1:
    st.header("Knowledge Base Upload")

    st.subheader("Upload New Document")
    uploaded = st.file_uploader("Choose a PDF, DOCX or TXT file", type=["pdf", "docx", "txt"])
    process = st.button("Process and Upload")

    if uploaded and process:
        file_bytes = uploaded.read()
        filename = uploaded.name
        file_ext = Path(filename).suffix.lower()

        with st.spinner("Extracting text..."):
            try:
                if file_ext == ".pdf":
                    from document_utils import extract_text_from_pdf

                    text = extract_text_from_pdf(file_bytes, filename)
                elif file_ext == ".docx":
                    from document_utils import extract_text_from_docx

                    text = extract_text_from_docx(file_bytes)
                else:
                    from document_utils import extract_text_from_txt

                    text = extract_text_from_txt(file_bytes)
            except Exception as e:
                st.error(f"Failed to extract text: {e}")
                text = ""

        st.write(f"Character count: {len(text)}")

        if len(text) < 50:
            st.error("Document too short to process (minimum 50 characters).")
        else:
            # derive product name from filename
            product_name = Path(filename).stem

            st.info(f"Product name: {product_name}")

            from document_utils import chunk_text

            chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
            st.write(f"Created {len(chunks)} chunks")

            # prefix each chunk
            chunk_texts = [f"Product: {product_name}\n\n" + c["content"] for c in chunks]

            # generate embeddings in batches with progress
            embeddings = []
            batch_size = 128
            total = len(chunk_texts)
            progress = st.progress(0)
            for i in range(0, total, batch_size):
                batch = chunk_texts[i : i + batch_size]
                with st.spinner(f"Generating embeddings for batch {i // batch_size + 1}..."):
                    try:
                        from embeddings_utils import create_embeddings_batch

                        batch_emb = create_embeddings_batch(batch, openai_client)
                    except Exception as e:
                        st.error(f"Embedding generation failed: {e}")
                        batch_emb = []
                embeddings.extend(batch_emb)
                progress.progress(min(1.0, len(embeddings) / max(1, total)))

            if len(embeddings) != total:
                st.error("Some embeddings failed to generate. Aborting upload.")
            else:
                # store in DB
                conn = get_db_conn()
                metadata = {"product_name": product_name}
                try:
                    doc_id = store_document_and_chunks(conn, filename, file_ext.lstrip('.'), "", chunks, embeddings, metadata)
                    st.success(f"Uploaded document with id {doc_id}")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to store document: {e}")

    st.divider()

    st.subheader("Existing Documents")
    conn = get_db_conn()
    docs = []
    try:
        docs = get_all_documents(conn)
    except Exception as e:
        st.error(f"Failed to query documents: {e}")

    if not docs:
        st.info("No documents uploaded yet.")
    else:
        for d in docs:
            cols = st.columns([3, 4, 2])
            cols[0].write(d["filename"])
            cols[1].write(f"ID: {d['id']} | Chunks: {d['total_chunks']} | Uploaded: {d['uploaded_at']}")
            if cols[2].button(f"Delete {d['id']}"):
                confirm = cols[2].button(f"Confirm delete {d['id']}")
                if confirm:
                    try:
                        delete_document(conn, d["id"])
                        st.success(f"Deleted document {d['id']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete document: {e}")
            st.divider()

with tab2:
    st.header("Chat")

    # -----------------------------
    # Sidebar: Model & Search configuration
    # -----------------------------
    st.sidebar.header("Model Settings")
    provider = st.sidebar.selectbox("Provider", ["OpenAI", "AWS Bedrock"], index=0)

    # Dynamic model choices
    if provider == "OpenAI":
        model_display = list(OPENAI_MODELS.keys())
        model_choice = st.sidebar.selectbox("Model", model_display, index=0)
        model_id = OPENAI_MODELS[model_choice]
        st.sidebar.info(f"Selected OpenAI model: {model_choice} -> {model_id}")
        # initialize OpenAI client
        client = get_openai_client()
    else:
        model_display = list(BEDROCK_MODELS.keys())
        model_choice = st.sidebar.selectbox("Model", model_display, index=0)
        model_id = BEDROCK_MODELS[model_choice]
        st.sidebar.info(f"Selected Bedrock model: {model_choice} -> {model_id}")
        # initialize Bedrock client
        client = bedrock_client or get_bedrock_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

    # Search settings
    st.sidebar.header("Search Settings")
    top_k = st.sidebar.slider("Top K", min_value=1, max_value=10, value=5, step=1)
    min_similarity = st.sidebar.slider("Min Similarity", min_value=0.0, max_value=1.0, value=0.4, step=0.05)

    # Enhanced embeddings
    st.sidebar.header("Enhanced Embeddings")
    use_enhanced = st.sidebar.checkbox("Use Enhanced Embeddings", value=False)
    embedding_type = "enhanced" if use_enhanced else "general"

    # Helpers for enhanced embedding counts
    def count_embeddings_by_type(conn, etype: str) -> int:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding_type = %s;", (etype,))
                return int(cur.fetchone()[0])
        except Exception:
            return 0

    conn = get_db_conn()
    enhanced_count = count_embeddings_by_type(conn, "enhanced")
    general_count = count_embeddings_by_type(conn, "general")

    if use_enhanced:
        if enhanced_count == 0:
            st.sidebar.warning("No enhanced embeddings found.")
            if st.sidebar.button("🚀 Generate Enhanced Embeddings"):
                st.sidebar.info("Starting generation of enhanced embeddings (this may take a while)...")
                progress = st.sidebar.progress(0)
                status_txt = st.sidebar.empty()

                def _progress_cb(info: dict):
                    try:
                        current = int(info.get("current", 0))
                        total = int(info.get("total", 1))
                        status = info.get("status", "")
                        message = info.get("message", "")
                        last_id = info.get("last_id")
                        frac = min(1.0, current / total) if total > 0 else 0.0
                        progress.progress(frac)
                        status_txt.text(f"{status} — {current}/{total} {message or ''} {f'last_id={last_id}' if last_id else ''}")
                    except Exception:
                        pass

                try:
                    from embeddings_utils import generate_enhanced_embeddings_for_all

                    res = generate_enhanced_embeddings_for_all(openai_client, progress_callback=_progress_cb)
                    if res.get("status") == "exists":
                        st.sidebar.info(f"Enhanced embeddings already exist: {res.get('count')}")
                    elif res.get("status") == "success":
                        st.sidebar.success(f"Generated enhanced embeddings for {res.get('count')} chunks")
                        st.rerun()
                    else:
                        st.sidebar.warning(f"Completed with status: {res.get('status')} count={res.get('count')}")
                except Exception as e:
                    st.sidebar.error(f"Failed to generate enhanced embeddings: {e}")
        else:
            st.sidebar.success(f"Enhanced embeddings available: {enhanced_count}")
            if st.sidebar.button("Recreate All Enhanced Embeddings"):
                confirm = st.sidebar.checkbox("Confirm recreate (this will overwrite existing enhanced embeddings)")
                if confirm:
                    st.sidebar.info("Recreating enhanced embeddings for all chunks...")
                    try:
                        from embeddings_utils import create_embeddings_batch

                        with conn.cursor() as cur:
                            cur.execute("SELECT id, content FROM document_chunks;")
                            rows = cur.fetchall()
                        texts = [r[1] for r in rows]
                        ids = [r[0] for r in rows]
                        batch_size = 128
                        progress = st.sidebar.progress(0)
                        updated = 0
                        for i in range(0, len(texts), batch_size):
                            batch_texts = texts[i : i + batch_size]
                            batch_ids = ids[i : i + batch_size]
                            batch_embs = create_embeddings_batch(batch_texts, openai_client)
                            with conn.cursor() as cur:
                                for bid, emb in zip(batch_ids, batch_embs):
                                    vec = _pg_vector_literal(emb)
                                    cur.execute("UPDATE document_chunks SET embedding = %s::vector, embedding_type = 'enhanced' WHERE id = %s;", (vec, int(bid)))
                                    updated += 1
                            progress.progress(min(1.0, updated / max(1, len(texts))))
                        st.sidebar.success(f"Recreated enhanced embeddings for {updated} chunks")
                        enhanced_count = count_embeddings_by_type(conn, "enhanced")
                    except Exception as e:
                        st.sidebar.error(f"Failed to recreate enhanced embeddings: {e}")

    else:
        st.sidebar.info(f"Using embedding type: general ({general_count} chunks)")

    # Expose variables for the main chat UI
    st.session_state.setdefault("provider", provider)
    st.session_state.setdefault("model_id", model_id)
    st.session_state.setdefault("client", client)
    st.session_state.setdefault("top_k", top_k)
    st.session_state.setdefault("min_similarity", min_similarity)
    st.session_state.setdefault("use_enhanced", use_enhanced)
    st.session_state.setdefault("embedding_type", embedding_type)

    # -----------------------------
    # Helper: search similar chunks
    # -----------------------------
    def search_similar_chunks(question: str, client, top_k: int, min_similarity: float, embedding_type: str, provider: str):
        from embeddings_utils import create_embedding

        q_emb = None
        try:
            # create embedding for the question
            q_emb = create_embedding(question, client)
        except Exception as e:
            raise RuntimeError(f"Failed to create question embedding: {e}")

        # Build SQL to search by nearest neighbors using pgvector <-> operator (distance)
        # We'll compute similarity as (1 - normalized_distance) for display; distances are non-negative.
        try:
            with get_db_conn().cursor() as cur:
                # Use the <-> operator to get nearest by distance
                cur.execute(
                    """
                    SELECT id, document_id, content, metadata, embedding <-> %s::vector AS distance
                    FROM document_chunks
                    WHERE embedding_type = %s
                    ORDER BY embedding <-> %s::vector
                    LIMIT %s
                    """,
                    (_pg_vector_literal(q_emb), embedding_type, _pg_vector_literal(q_emb), top_k),
                )
                rows = cur.fetchall()
        except Exception as e:
            raise RuntimeError(f"Failed to run similarity search: {e}")

        # Convert rows to structured chunks with similarity score
        chunks = []
        # Compute a naive similarity from distance: similarity = 1 / (1 + distance)
        for r in rows:
            _id, doc_id, content, metadata, distance = r
            try:
                similarity = float(1.0 / (1.0 + float(distance)))
            except Exception:
                similarity = 0.0
            chunks.append({
                "id": _id,
                "document_id": doc_id,
                "content": content,
                "metadata": metadata if metadata else {},
                "distance": float(distance),
                "similarity": similarity,
            })

        # Filter by min_similarity
        filtered = [c for c in chunks if c["similarity"] >= min_similarity]
        return filtered, q_emb

    # -----------------------------
    # Main Chat UI (3-column responses)
    # -----------------------------
    st.subheader("Ask the knowledge base")
    cols = st.columns([6, 6, 6])

    # Input area
    with st.form(key="chat_form"):
        question = st.text_input("Ask a question", placeholder="e.g., What are the features of AMI smart meters?", key="chat_input")
        submit = st.form_submit_button("Send")

    if "last_question" not in st.session_state:
        st.session_state["last_question"] = None

    if submit:
        if not question or question.strip() == "":
            st.warning("Please enter a question.")
        elif question.strip() == st.session_state.get("last_question"):
            st.info("You've already asked that question — modify it or wait for results.")
        else:
            st.session_state["last_question"] = question.strip()

            # Prepare containers for results reuse
            results = {"without": None, "with": None, "guard": None}

            # Column 1: Without Context
            with cols[0].container():
                cols[0].header("🔵 Without Context")
                try:
                    ans, elapsed = generate_response_without_context(question, st.session_state["model_id"], st.session_state["client"], st.session_state["provider"])
                    st.write(ans)
                    st.caption(f"Response time: {elapsed:.2f}s")
                    results["without"] = {"answer": ans, "time": elapsed}
                except Exception as e:
                    st.error(f"Without-context error: {e}")

            # Column 2: With Context
            with cols[1].container():
                cols[1].header("🟢 With Context")
                try:
                    search_t0 = time.time()
                    chunks, q_emb = search_similar_chunks(question, openai_client, st.session_state["top_k"], st.session_state["min_similarity"], st.session_state["embedding_type"], st.session_state["provider"])
                    search_t1 = time.time()
                    search_time = search_t1 - search_t0

                    # Debug: summary info box with similarities
                    sims = [f"{c['similarity']:.3f}" for c in chunks]
                    st.info(f"🔍 Found {len(chunks)} relevant chunks with similarities: {sims}")

                    if len(chunks) > 0:
                        # Expandable debug viewer showing brief previews per chunk
                        with st.expander("🔍 View Retrieved Context (Debug)"):
                            for i, c in enumerate(chunks, start=1):
                                meta = c.get("metadata", {})
                                src = meta.get("source_filename") or meta.get("filename") or "unknown"
                                product = meta.get("product") or meta.get("product_name") or "-"
                                preview = c["content"][0:300].replace("\n", " ")
                                st.markdown(f"**Chunk {i}** — similarity: {c['similarity']:.3f}")
                                st.markdown(f"*Filename:* {src}")
                                st.markdown(f"*Product:* {product}")
                                st.text(preview + ("..." if len(c["content"]) > 300 else ""))
                                st.markdown("---")

                    # call LLM with context
                    answer_with, gen_time = generate_response_with_context(question, chunks, st.session_state["model_id"], st.session_state["client"], st.session_state["provider"])
                    total_time = gen_time + search_time
                    st.write(answer_with)
                    st.caption(f"Search time: {search_time:.2f}s — Total response time: {total_time:.2f}s")
                    results["with"] = {"answer": answer_with, "time": total_time, "search_time": search_time, "chunks": chunks}
                except Exception as e:
                    st.error(f"With-context error: {e}")

            # Column 3: With Context + Guardrail
            with cols[2].container():
                cols[2].header("🟡 With Context + Guardrail")
                try:
                    # reuse chunks from column 2 if available
                    guard_chunks = None
                    if results.get("with") and results["with"].get("chunks"):
                        guard_chunks = results["with"]["chunks"]
                    else:
                        guard_chunks, q_emb = search_similar_chunks(question, openai_client, st.session_state["top_k"], st.session_state["min_similarity"], st.session_state["embedding_type"], st.session_state["provider"])

                    ans_guard, g_total = generate_response_with_guardrail(question, guard_chunks, st.session_state["model_id"], st.session_state["client"], st.session_state["provider"])
                    st.write(ans_guard)
                    st.caption(f"Total response time: {g_total:.2f}s")
                    results["guard"] = {"answer": ans_guard, "time": g_total, "chunks": guard_chunks}
                except Exception as e:
                    st.error(f"Guardrail error: {e}")

            # Bottom: Retrieved Context Display
            if results.get("with") and results["with"].get("chunks"):
                all_chunks = results["with"]["chunks"]
                if all_chunks:
                    st.divider()
                    st.header("📚 Retrieved Context")
                    st.caption(f"Search time: {results['with']['search_time']:.2f}s | Found {len(all_chunks)} relevant chunks")
                    formatted = []
                    for i, c in enumerate(all_chunks, start=1):
                        meta = c.get("metadata", {})
                        src = meta.get("source_filename") or meta.get("filename") or "unknown"
                        product = meta.get("product") or meta.get("product_name") or "-"
                        formatted.append(f"**Chunk {i}** (Similarity: {c['similarity']:.3f})")
                        formatted.append(f"*Source: {src} - {product}*\n")
                        formatted.append(c["content"])
                        formatted.append("\n---\n")
                    st.text_area("Retrieved context (full)", value="\n".join(formatted), height=400)

