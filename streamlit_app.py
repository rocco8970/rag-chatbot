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
import boto3
from dotenv import load_dotenv

import pdfplumber
import docx

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from response_generation import (
    generate_response_without_context,
    generate_response_with_context,
    generate_response_with_guardrail,
)

# ═══════════════════════════════════════════════════════════════════
# AUTO-DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════════
# Reads .env once at startup. No code changes ever needed.
# Priority: Bedrock (if AWS keys set) → OpenAI (if key set) → error
# ═══════════════════════════════════════════════════════════════════
load_dotenv()

# ── Raw credentials from .env ──
OPENAI_API_KEY        = os.getenv("OPENAI_API_KEY", "").strip()
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
AWS_REGION            = os.getenv("AWS_REGION", "ap-south-1").strip()

# ── Availability flags ──
_HAS_OPENAI  = bool(OpenAI and OPENAI_API_KEY)
_HAS_BEDROCK = bool(
    AWS_ACCESS_KEY_ID
    and AWS_SECRET_ACCESS_KEY
    and AWS_ACCESS_KEY_ID not in ("YOUR_AWS_ACCESS_KEY_ID", "")
    and AWS_SECRET_ACCESS_KEY not in ("YOUR_AWS_SECRET_ACCESS_KEY", "")
)

# ── Auto-select active provider (Bedrock wins if both set) ──
if _HAS_BEDROCK:
    ACTIVE_PROVIDER   = "AWS Bedrock"
    ACTIVE_EMBED_PROV = "bedrock"
elif _HAS_OPENAI:
    ACTIVE_PROVIDER   = "OpenAI"
    ACTIVE_EMBED_PROV = "openai"
else:
    ACTIVE_PROVIDER   = "none"
    ACTIVE_EMBED_PROV = "none"

# ── Database ──
DB_HOST     = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT     = int(os.getenv("DB_PORT", "5432"))
DB_NAME     = os.getenv("DB_NAME", "postgres")
DB_USER     = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# ── Chunking ──
CHUNK_SIZE    = int(os.getenv("RAG_CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))
EMBEDDING_DIM = 1536

# ── Model menus (shown in sidebar based on active provider) ──
OPENAI_MODELS: Dict[str, str] = {
    "GPT-4o Mini  ⚡": "gpt-4o-mini",
    "GPT-4o  🧠":      "gpt-4o",
    "GPT-3.5 Turbo":   "gpt-3.5-turbo",
}

BEDROCK_MODELS: Dict[str, str] = {
    "Claude 3.5 Sonnet v2  🏆": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "Claude 3.5 Sonnet  ⚡":    "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "Claude 3 Haiku  💨":       "anthropic.claude-3-haiku-20240307-v1:0",
    "Claude 3 Sonnet":          "anthropic.claude-3-sonnet-20240229-v1:0",
}

# ─────────────────────────────────────────────
# Page config  (must be first Streamlit call)
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="NeuralQuery — RAG Intelligence Platform",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Global CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Root palette ── */
:root {
  --bg-primary:    #0a0e1a;
  --bg-secondary:  #0f1629;
  --bg-card:       #131929;
  --bg-card-hover: #1a2235;
  --accent-blue:   #4f8ef7;
  --accent-purple: #8b5cf6;
  --accent-cyan:   #06b6d4;
  --accent-green:  #10b981;
  --accent-amber:  #f59e0b;
  --accent-red:    #ef4444;
  --border:        rgba(79,142,247,0.18);
  --border-hover:  rgba(79,142,247,0.45);
  --text-primary:  #e8eaf6;
  --text-secondary:#94a3b8;
  --text-muted:    #64748b;
  --glow-blue:     0 0 24px rgba(79,142,247,0.25);
  --glow-purple:   0 0 24px rgba(139,92,246,0.25);
  --radius-lg:     16px;
  --radius-md:     10px;
  --radius-sm:     6px;
}

/* ── Base ── */
html, body, [class*="css"] {
  font-family: 'Inter', sans-serif !important;
  background-color: var(--bg-primary) !important;
  color: var(--text-primary) !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── Main container ── */
.main .block-container {
  padding: 0 2rem 3rem 2rem !important;
  max-width: 1600px !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #0d1220 0%, #0a0e1a 100%) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] .block-container { padding: 1.5rem 1rem !important; }

/* ── Sidebar labels ── */
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stSlider label {
  color: var(--text-secondary) !important;
  font-size: 0.78rem !important;
  font-weight: 500 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
}

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
}
[data-testid="stSelectbox"] > div > div:hover {
  border-color: var(--accent-blue) !important;
}

/* ── Slider ── */
[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
  background: var(--accent-blue) !important;
  box-shadow: var(--glow-blue) !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
  background: var(--bg-secondary) !important;
  border-radius: var(--radius-lg) !important;
  padding: 4px !important;
  gap: 4px !important;
  border: 1px solid var(--border) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  background: transparent !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-secondary) !important;
  font-weight: 500 !important;
  font-size: 0.9rem !important;
  padding: 0.55rem 1.4rem !important;
  transition: all 0.2s ease !important;
}
[data-testid="stTabs"] [aria-selected="true"] {
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple)) !important;
  color: #fff !important;
  box-shadow: var(--glow-blue) !important;
}

/* ── Buttons ── */
.stButton > button {
  background: linear-gradient(135deg, var(--accent-blue) 0%, var(--accent-purple) 100%) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: 0.88rem !important;
  padding: 0.55rem 1.4rem !important;
  letter-spacing: 0.03em !important;
  transition: all 0.25s ease !important;
  box-shadow: 0 4px 15px rgba(79,142,247,0.3) !important;
}
.stButton > button:hover {
  transform: translateY(-2px) !important;
  box-shadow: 0 8px 25px rgba(79,142,247,0.45) !important;
}
.stButton > button:active { transform: translateY(0) !important; }

/* ── File uploader ── */
[data-testid="stFileUploader"] {
  background: var(--bg-card) !important;
  border: 2px dashed var(--border) !important;
  border-radius: var(--radius-lg) !important;
  transition: border-color 0.2s ease !important;
}
[data-testid="stFileUploader"]:hover {
  border-color: var(--accent-blue) !important;
}

/* ── Text input ── */
[data-testid="stTextInput"] input {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 0.95rem !important;
  padding: 0.7rem 1rem !important;
  transition: border-color 0.2s ease !important;
}
[data-testid="stTextInput"] input:focus {
  border-color: var(--accent-blue) !important;
  box-shadow: 0 0 0 3px rgba(79,142,247,0.15) !important;
}

/* ── Text area ── */
textarea {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
  color: var(--text-primary) !important;
  font-size: 0.85rem !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div {
  background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)) !important;
  border-radius: 99px !important;
}
[data-testid="stProgressBar"] > div {
  background: var(--bg-card) !important;
  border-radius: 99px !important;
}

/* ── Expander ── */
[data-testid="stExpander"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius-md) !important;
}
[data-testid="stExpander"] summary {
  color: var(--text-secondary) !important;
  font-weight: 500 !important;
}

/* ── Alerts ── */
[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
  border-left-width: 4px !important;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; margin: 1.5rem 0 !important; }

/* ── Checkbox ── */
[data-testid="stCheckbox"] label { color: var(--text-secondary) !important; font-size: 0.85rem !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--bg-primary); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
::-webkit-scrollbar-thumb:hover { background: var(--accent-blue); }

/* ── Custom component classes ── */
.nq-hero {
  background: linear-gradient(135deg, #0d1220 0%, #111827 50%, #0d1220 100%);
  border-bottom: 1px solid var(--border);
  padding: 2rem 2rem 1.5rem 2rem;
  margin: -1rem -2rem 2rem -2rem;
  position: relative;
  overflow: hidden;
}
.nq-hero::before {
  content: '';
  position: absolute;
  top: -60px; left: -60px;
  width: 320px; height: 320px;
  background: radial-gradient(circle, rgba(79,142,247,0.12) 0%, transparent 70%);
  pointer-events: none;
}
.nq-hero::after {
  content: '';
  position: absolute;
  bottom: -80px; right: -40px;
  width: 280px; height: 280px;
  background: radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 70%);
  pointer-events: none;
}
.nq-logo-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 0.4rem;
}
.nq-logo-icon {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #4f8ef7, #8b5cf6);
  border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.6rem;
  box-shadow: 0 4px 20px rgba(79,142,247,0.4);
  flex-shrink: 0;
}
.nq-brand-name {
  font-size: 1.75rem;
  font-weight: 800;
  background: linear-gradient(135deg, #4f8ef7 0%, #8b5cf6 50%, #06b6d4 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: -0.02em;
  line-height: 1;
}
.nq-brand-tagline {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-weight: 400;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-top: 2px;
}
.nq-hero-desc {
  color: var(--text-secondary);
  font-size: 0.9rem;
  max-width: 600px;
  line-height: 1.6;
  margin-top: 0.5rem;
}
.nq-badge-row {
  display: flex;
  gap: 8px;
  margin-top: 1rem;
  flex-wrap: wrap;
}
.nq-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 99px;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  border: 1px solid;
}
.nq-badge-blue  { color: var(--accent-blue);   border-color: rgba(79,142,247,0.35);  background: rgba(79,142,247,0.08); }
.nq-badge-purple{ color: var(--accent-purple); border-color: rgba(139,92,246,0.35); background: rgba(139,92,246,0.08); }
.nq-badge-cyan  { color: var(--accent-cyan);   border-color: rgba(6,182,212,0.35);  background: rgba(6,182,212,0.08); }
.nq-badge-green { color: var(--accent-green);  border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.08); }

.nq-section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 0.2rem;
  display: flex;
  align-items: center;
  gap: 8px;
}
.nq-section-sub {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 1.2rem;
}

.nq-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.4rem 1.5rem;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.nq-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--glow-blue);
}

.nq-doc-row {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.85rem 1.1rem;
  margin-bottom: 0.6rem;
  transition: border-color 0.2s ease;
}
.nq-doc-row:hover { border-color: var(--border-hover); }
.nq-doc-icon {
  width: 36px; height: 36px;
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem;
  flex-shrink: 0;
}
.nq-doc-icon-pdf    { background: rgba(239,68,68,0.15);  color: #ef4444; }
.nq-doc-icon-docx   { background: rgba(79,142,247,0.15); color: #4f8ef7; }
.nq-doc-icon-txt    { background: rgba(16,185,129,0.15); color: #10b981; }
.nq-doc-icon-other  { background: rgba(148,163,184,0.15);color: #94a3b8; }
.nq-doc-name  { font-size: 0.88rem; font-weight: 600; color: var(--text-primary); }
.nq-doc-meta  { font-size: 0.75rem; color: var(--text-muted); margin-top: 1px; }

.nq-stat-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(79,142,247,0.1);
  border: 1px solid rgba(79,142,247,0.2);
  border-radius: 99px;
  padding: 2px 9px;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--accent-blue);
}

.nq-response-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.3rem 1.4rem;
  height: 100%;
  position: relative;
  overflow: hidden;
}
.nq-response-card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}
.nq-rc-blue::before   { background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan)); }
.nq-rc-green::before  { background: linear-gradient(90deg, var(--accent-green), var(--accent-cyan)); }
.nq-rc-amber::before  { background: linear-gradient(90deg, var(--accent-amber), #f97316); }

.nq-response-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border);
}
.nq-response-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.nq-response-title {
  font-size: 0.88rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}
.nq-response-badge {
  margin-left: auto;
  font-size: 0.68rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 99px;
}
.nq-rb-blue   { background: rgba(79,142,247,0.15);  color: var(--accent-blue);   border: 1px solid rgba(79,142,247,0.3); }
.nq-rb-green  { background: rgba(16,185,129,0.15);  color: var(--accent-green);  border: 1px solid rgba(16,185,129,0.3); }
.nq-rb-amber  { background: rgba(245,158,11,0.15);  color: var(--accent-amber);  border: 1px solid rgba(245,158,11,0.3); }

.nq-response-body {
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--text-secondary);
  min-height: 80px;
}
.nq-response-footer {
  margin-top: 1rem;
  padding-top: 0.6rem;
  border-top: 1px solid var(--border);
  font-size: 0.72rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
}

.nq-chunk-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 0.9rem 1rem;
  margin-bottom: 0.6rem;
}
.nq-chunk-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 0.5rem;
}
.nq-chunk-num {
  background: linear-gradient(135deg, var(--accent-blue), var(--accent-purple));
  color: #fff;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 99px;
}
.nq-chunk-sim {
  font-size: 0.72rem;
  color: var(--accent-green);
  font-weight: 600;
}
.nq-chunk-src {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-left: auto;
}
.nq-chunk-text {
  font-size: 0.8rem;
  color: var(--text-secondary);
  line-height: 1.6;
}

.nq-empty-state {
  text-align: center;
  padding: 3rem 1rem;
  color: var(--text-muted);
}
.nq-empty-icon { font-size: 3rem; margin-bottom: 0.8rem; }
.nq-empty-title { font-size: 1rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 0.4rem; }
.nq-empty-desc  { font-size: 0.82rem; }

.nq-sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0.5rem 0 1.2rem 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1.2rem;
}
.nq-sidebar-logo-icon {
  width: 36px; height: 36px;
  background: linear-gradient(135deg, #4f8ef7, #8b5cf6);
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.2rem;
  box-shadow: 0 2px 12px rgba(79,142,247,0.35);
}
.nq-sidebar-brand {
  font-size: 1.05rem;
  font-weight: 800;
  background: linear-gradient(135deg, #4f8ef7, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.nq-sidebar-version {
  font-size: 0.65rem;
  color: var(--text-muted);
  letter-spacing: 0.06em;
}

.nq-section-divider {
  border: none;
  border-top: 1px solid var(--border);
  margin: 1rem 0;
}

.nq-status-dot {
  display: inline-block;
  width: 7px; height: 7px;
  border-radius: 50%;
  background: var(--accent-green);
  box-shadow: 0 0 6px var(--accent-green);
  margin-right: 5px;
}

.nq-query-box {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.4rem 1.5rem;
  margin-bottom: 1.5rem;
}
.nq-query-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.07em;
  text-transform: uppercase;
  margin-bottom: 0.6rem;
}

.nq-sim-bar-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}
.nq-sim-bar-bg {
  flex: 1;
  height: 4px;
  background: var(--bg-secondary);
  border-radius: 99px;
  overflow: hidden;
}
.nq-sim-bar-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--accent-blue), var(--accent-green));
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Cached client factories
# ─────────────────────────────────────────────
@st.cache_resource
def get_openai_client(api_key: Optional[str] = None):
    """Return OpenAI client only if a key is available, else None."""
    key = api_key or OPENAI_API_KEY
    if not key:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None


@st.cache_resource
def get_bedrock_client(
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    region_name: Optional[str] = None,
):
    region = region_name or AWS_REGION
    kwargs = {"region_name": region}
    if aws_access_key_id and aws_secret_access_key:
        kwargs["aws_access_key_id"] = aws_access_key_id
        kwargs["aws_secret_access_key"] = aws_secret_access_key
    return boto3.client("bedrock-runtime", **kwargs)


# ─────────────────────────────────────────────
# Initialize clients
# ─────────────────────────────────────────────
openai_client = get_openai_client()
bedrock_client = None
try:
    bedrock_client = get_bedrock_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)
except Exception:
    bedrock_client = None

def _get_embed_client_and_provider():
    """Return (client, provider_str) to use for embeddings.
    Prefers Bedrock if credentials are set, falls back to OpenAI."""
    if bedrock_client is not None and AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return bedrock_client, "bedrock"
    return openai_client, "openai"


# ─────────────────────────────────────────────
# Database helpers
# ─────────────────────────────────────────────
@st.cache_resource
def get_db_conn():
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    conn.autocommit = True
    return conn


def _pg_vector_literal(emb):
    return "[" + ",".join(str(float(x)) for x in emb) + "]"


def store_document_and_chunks(conn, filename, file_type, file_path, chunks, embeddings, metadata=None, embedding_type="general"):
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
    return [{"id": r[0], "filename": r[1], "total_chunks": r[2], "uploaded_at": r[3], "metadata": r[4]} for r in rows]


def delete_document(conn, doc_id: int):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM company_documents WHERE id = %s;", (int(doc_id),))
    return True


def count_embeddings_by_type(conn, etype: str) -> int:
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding_type = %s;", (etype,))
            return int(cur.fetchone()[0])
    except Exception:
        return 0


# ─────────────────────────────────────────────
# Helper: similarity search
# ─────────────────────────────────────────────
def search_similar_chunks(question, client, top_k, min_similarity, embedding_type, provider):
    from embeddings_utils import create_embedding
    embed_provider = "bedrock" if provider.lower() in ("bedrock", "aws bedrock", "aws") else "openai"
    q_emb = create_embedding(question, client, provider=embed_provider)
    with get_db_conn().cursor() as cur:
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
    chunks = []
    for r in rows:
        _id, doc_id, content, metadata, distance = r
        try:
            similarity = float(1.0 / (1.0 + float(distance)))
        except Exception:
            similarity = 0.0
        chunks.append({
            "id": _id, "document_id": doc_id, "content": content,
            "metadata": metadata if metadata else {},
            "distance": float(distance), "similarity": similarity,
        })
    return [c for c in chunks if c["similarity"] >= min_similarity], q_emb


# ─────────────────────────────────────────────
# Helper: doc icon by extension
# ─────────────────────────────────────────────
def _doc_icon_class(filename: str) -> tuple:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return "nq-doc-icon-pdf", "📄"
    elif ext in (".docx", ".doc"):
        return "nq-doc-icon-docx", "📝"
    elif ext == ".txt":
        return "nq-doc-icon-txt", "📃"
    return "nq-doc-icon-other", "📁"


# ═══════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════
with st.sidebar:
    # Logo
    st.markdown("""
    <div class="nq-sidebar-logo">
      <div class="nq-sidebar-logo-icon">🧬</div>
      <div>
        <div class="nq-sidebar-brand">NeuralQuery</div>
        <div class="nq-sidebar-version">v1.0 · RAG Platform</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Status
    _ec_check, _ep_check = _get_embed_client_and_provider()
    _embed_label = "Bedrock Titan v2" if _ep_check == "bedrock" else "OpenAI text-embedding-3-small"
    _embed_color = "#8b5cf6" if _ep_check == "bedrock" else "#4f8ef7"
    st.markdown(f"""
    <div style="font-size:0.75rem; color:#64748b; margin-bottom:1.2rem; line-height:1.8;">
      <span class="nq-status-dot"></span>All systems operational<br>
      <span style="font-size:0.7rem;">🔢 Embeddings: <span style="color:{_embed_color};">{_embed_label}</span></span>
    </div>
    """, unsafe_allow_html=True)

    # ── AWS credentials check ──
    _aws_ready = bool(AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
                      and AWS_ACCESS_KEY_ID != "YOUR_AWS_ACCESS_KEY_ID")
    if not _aws_ready:
        st.markdown("""
        <div style="background:rgba(245,158,11,0.1);border:1px solid rgba(245,158,11,0.35);
                    border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:0.8rem;font-size:0.75rem;
                    color:#f59e0b;line-height:1.6;">
          ⚠️ <strong>AWS credentials not set.</strong><br>
          Edit <code>.env</code> and add your<br>
          <code>AWS_ACCESS_KEY_ID</code> and<br>
          <code>AWS_SECRET_ACCESS_KEY</code>
        </div>
        """, unsafe_allow_html=True)

    # ── AI Provider ──
    st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.4rem;">AI Provider</div>', unsafe_allow_html=True)
    _default_provider_idx = 1 if _aws_ready else 0
    provider = st.selectbox("Provider", ["OpenAI", "AWS Bedrock"], index=_default_provider_idx, label_visibility="collapsed")

    if provider == "OpenAI":
        model_display = list(OPENAI_MODELS.keys())
        st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;margin:0.8rem 0 0.4rem 0;">Model</div>', unsafe_allow_html=True)
        model_choice = st.selectbox("Model", model_display, index=0, label_visibility="collapsed")
        model_id = OPENAI_MODELS[model_choice]
        st.markdown(f'<div style="font-size:0.72rem;color:#4f8ef7;margin-bottom:0.8rem;">→ {model_id}</div>', unsafe_allow_html=True)
        client = get_openai_client()
    else:
        model_display = list(BEDROCK_MODELS.keys())
        st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;margin:0.8rem 0 0.4rem 0;">Model</div>', unsafe_allow_html=True)
        model_choice = st.selectbox("Model", model_display, index=0, label_visibility="collapsed")
        model_id = BEDROCK_MODELS[model_choice]
        st.markdown(f'<div style="font-size:0.72rem;color:#8b5cf6;margin-bottom:0.8rem;">→ {model_id}</div>', unsafe_allow_html=True)
        client = bedrock_client or get_bedrock_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)

    st.markdown('<hr class="nq-section-divider">', unsafe_allow_html=True)

    # ── Retrieval Settings ──
    st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.8rem;">Retrieval Settings</div>', unsafe_allow_html=True)
    top_k = st.slider("Top-K Results", min_value=1, max_value=10, value=5, step=1)
    min_similarity = st.slider("Min Similarity Score", min_value=0.0, max_value=1.0, value=0.4, step=0.05)

    st.markdown('<hr class="nq-section-divider">', unsafe_allow_html=True)

    # ── Enhanced Embeddings ──
    st.markdown('<div style="font-size:0.72rem;font-weight:600;color:#64748b;letter-spacing:0.07em;text-transform:uppercase;margin-bottom:0.6rem;">Embedding Mode</div>', unsafe_allow_html=True)
    use_enhanced = st.checkbox("Use Enhanced Embeddings", value=False)
    embedding_type = "enhanced" if use_enhanced else "general"

    conn_sb = get_db_conn()
    enhanced_count = count_embeddings_by_type(conn_sb, "enhanced")
    general_count  = count_embeddings_by_type(conn_sb, "general")

    if use_enhanced:
        if enhanced_count == 0:
            st.warning("No enhanced embeddings found.")
            if st.button("🚀 Generate Enhanced Embeddings"):
                st.info("Generating enhanced embeddings…")
                progress_sb = st.progress(0)
                status_txt  = st.empty()

                def _progress_cb(info: dict):
                    try:
                        current = int(info.get("current", 0))
                        total   = int(info.get("total", 1))
                        frac    = min(1.0, current / total) if total > 0 else 0.0
                        progress_sb.progress(frac)
                        status_txt.text(f"{current}/{total} chunks processed")
                    except Exception:
                        pass

                try:
                    from embeddings_utils import generate_enhanced_embeddings_for_all
                    _ec, _ep = _get_embed_client_and_provider()
                    res = generate_enhanced_embeddings_for_all(_ec, provider=_ep, progress_callback=_progress_cb)
                    if res.get("status") == "exists":
                        st.info(f"Already exists: {res.get('count')} chunks")
                    elif res.get("status") == "success":
                        st.success(f"Generated {res.get('count')} enhanced embeddings")
                        st.rerun()
                    else:
                        st.warning(f"Status: {res.get('status')}")
                except Exception as e:
                    st.error(f"Failed: {e}")
        else:
            st.markdown(f'<div class="nq-stat-pill">✦ {enhanced_count} enhanced chunks</div>', unsafe_allow_html=True)
            if st.button("Recreate Enhanced Embeddings"):
                confirm = st.checkbox("Confirm overwrite")
                if confirm:
                    try:
                        from embeddings_utils import create_embeddings_batch
                        _ec, _ep = _get_embed_client_and_provider()
                        with conn_sb.cursor() as cur:
                            cur.execute("SELECT id, content FROM document_chunks;")
                            rows = cur.fetchall()
                        texts = [r[1] for r in rows]
                        ids   = [r[0] for r in rows]
                        batch_size = 128
                        prog = st.progress(0)
                        updated = 0
                        for i in range(0, len(texts), batch_size):
                            bt = texts[i:i+batch_size]
                            bi = ids[i:i+batch_size]
                            be = create_embeddings_batch(bt, _ec, provider=_ep)
                            with conn_sb.cursor() as cur:
                                for bid, emb in zip(bi, be):
                                    vec = _pg_vector_literal(emb)
                                    cur.execute("UPDATE document_chunks SET embedding=%s::vector, embedding_type='enhanced' WHERE id=%s;", (vec, int(bid)))
                                    updated += 1
                            prog.progress(min(1.0, updated / max(1, len(texts))))
                        st.success(f"Recreated {updated} enhanced embeddings")
                    except Exception as e:
                        st.error(f"Failed: {e}")
    else:
        st.markdown(f'<div class="nq-stat-pill">◈ {general_count} general chunks</div>', unsafe_allow_html=True)

    st.markdown('<hr class="nq-section-divider">', unsafe_allow_html=True)

    # ── Footer ──
    st.markdown("""
    <div style="font-size:0.7rem; color:#374151; text-align:center; padding-top:0.5rem; line-height:1.8;">
      Powered by <span style="color:#8b5cf6;">AWS Bedrock</span> &amp; <span style="color:#06b6d4;">pgvector</span><br>
      © 2025 NeuralQuery · All rights reserved
    </div>
    """, unsafe_allow_html=True)

    # Persist to session state
    st.session_state["provider"]       = provider
    st.session_state["model_id"]       = model_id
    st.session_state["client"]         = client
    st.session_state["top_k"]          = top_k
    st.session_state["min_similarity"] = min_similarity
    st.session_state["use_enhanced"]   = use_enhanced
    st.session_state["embedding_type"] = embedding_type


# ═══════════════════════════════════════════════
# HERO HEADER
# ═══════════════════════════════════════════════
st.markdown("""
<div class="nq-hero">
  <div class="nq-logo-row">
    <div class="nq-logo-icon">🧬</div>
    <div>
      <div class="nq-brand-name">NeuralQuery</div>
      <div class="nq-brand-tagline">RAG Intelligence Platform</div>
    </div>
  </div>
  <div class="nq-hero-desc">
    Enterprise-grade Retrieval-Augmented Generation — upload your documents, ask questions,
    and compare AI responses with and without grounded knowledge context.
  </div>
  <div class="nq-badge-row">
    <span class="nq-badge nq-badge-blue">⚡ OpenAI GPT-4o</span>
    <span class="nq-badge nq-badge-purple">🔮 AWS Bedrock</span>
    <span class="nq-badge nq-badge-cyan">🗄️ pgvector</span>
    <span class="nq-badge nq-badge-green">🛡️ Guardrail Mode</span>
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════
tab1, tab2 = st.tabs(["  📚  Knowledge Base  ", "  💬  Chat Interface  "])


# ───────────────────────────────────────────────
# TAB 1 — Knowledge Base
# ───────────────────────────────────────────────
with tab1:
    col_upload, col_docs = st.columns([1, 1], gap="large")

    # ── Left: Upload ──
    with col_upload:
        st.markdown("""
        <div class="nq-section-title">📤 Upload Document</div>
        <div class="nq-section-sub">Supported formats: PDF, DOCX, TXT · Max recommended: 50 MB</div>
        """, unsafe_allow_html=True)

        uploaded = st.file_uploader(
            "Drop your file here or click to browse",
            type=["pdf", "docx", "txt"],
            label_visibility="collapsed",
        )

        if uploaded:
            ext = Path(uploaded.name).suffix.lower()
            icon_cls, icon_char = _doc_icon_class(uploaded.name)
            size_kb = len(uploaded.getvalue()) / 1024
            st.markdown(f"""
            <div class="nq-doc-row" style="margin-top:0.8rem;">
              <div class="nq-doc-icon {icon_cls}">{icon_char}</div>
              <div>
                <div class="nq-doc-name">{uploaded.name}</div>
                <div class="nq-doc-meta">{ext.upper().lstrip('.')} · {size_kb:.1f} KB</div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        process = st.button("⚙️  Process & Embed Document", use_container_width=True)

        if uploaded and process:
            file_bytes = uploaded.read()
            filename   = uploaded.name
            file_ext   = Path(filename).suffix.lower()

            with st.spinner("Extracting text from document…"):
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
                    st.error(f"Text extraction failed: {e}")
                    text = ""

            if len(text) < 50:
                st.error("Document too short (minimum 50 characters). Please upload a valid document.")
            else:
                product_name = Path(filename).stem
                st.markdown(f"""
                <div style="display:flex;gap:12px;margin:0.8rem 0;flex-wrap:wrap;">
                  <span class="nq-stat-pill">📝 {len(text):,} characters</span>
                  <span class="nq-stat-pill">🏷️ {product_name}</span>
                </div>
                """, unsafe_allow_html=True)

                from document_utils import chunk_text
                chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
                chunk_texts = [f"Product: {product_name}\n\n" + c["content"] for c in chunks]

                st.markdown(f'<div class="nq-stat-pill" style="margin-bottom:0.8rem;">🔢 {len(chunks)} chunks created</div>', unsafe_allow_html=True)

                embeddings = []
                batch_size = 128
                total      = len(chunk_texts)
                prog_bar   = st.progress(0, text="Generating embeddings…")

                for i in range(0, total, batch_size):
                    batch = chunk_texts[i:i+batch_size]
                    try:
                        from embeddings_utils import create_embeddings_batch
                        _ec, _ep = _get_embed_client_and_provider()
                        batch_emb = create_embeddings_batch(batch, _ec, provider=_ep)
                    except Exception as e:
                        st.error(f"Embedding failed: {e}")
                        batch_emb = []
                    embeddings.extend(batch_emb)
                    pct = min(1.0, len(embeddings) / max(1, total))
                    prog_bar.progress(pct, text=f"Embedding {len(embeddings)}/{total} chunks…")

                if len(embeddings) != total:
                    st.error("Some embeddings failed. Aborting upload.")
                else:
                    conn_t1 = get_db_conn()
                    metadata = {"product_name": product_name}
                    try:
                        doc_id = store_document_and_chunks(conn_t1, filename, file_ext.lstrip('.'), "", chunks, embeddings, metadata)
                        st.success(f"✅ Document indexed successfully — ID #{doc_id}")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Storage failed: {e}")

    # ── Right: Document Library ──
    with col_docs:
        st.markdown("""
        <div class="nq-section-title">🗂️ Document Library</div>
        <div class="nq-section-sub">All indexed documents available for retrieval</div>
        """, unsafe_allow_html=True)

        conn_t1b = get_db_conn()
        docs = []
        try:
            docs = get_all_documents(conn_t1b)
        except Exception as e:
            st.error(f"Failed to load documents: {e}")

        if not docs:
            st.markdown("""
            <div class="nq-empty-state">
              <div class="nq-empty-icon">📭</div>
              <div class="nq-empty-title">No documents yet</div>
              <div class="nq-empty-desc">Upload a PDF, DOCX, or TXT file to get started</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="nq-stat-pill" style="margin-bottom:1rem;">📚 {len(docs)} document{"s" if len(docs)!=1 else ""} indexed</div>', unsafe_allow_html=True)
            for d in docs:
                icon_cls, icon_char = _doc_icon_class(d["filename"])
                uploaded_str = d["uploaded_at"].strftime("%b %d, %Y · %H:%M") if d["uploaded_at"] else "—"
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(f"""
                    <div class="nq-doc-row">
                      <div class="nq-doc-icon {icon_cls}">{icon_char}</div>
                      <div style="flex:1;min-width:0;">
                        <div class="nq-doc-name" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{d["filename"]}</div>
                        <div class="nq-doc-meta">ID #{d["id"]} · {d["total_chunks"]} chunks · {uploaded_str}</div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_del:
                    if st.button("🗑️", key=f"del_{d['id']}", help=f"Delete {d['filename']}"):
                        try:
                            delete_document(conn_t1b, d["id"])
                            st.success(f"Deleted #{d['id']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")


# ───────────────────────────────────────────────
# TAB 2 — Chat Interface
# ───────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="nq-section-title">💬 Intelligent Query Interface</div>
    <div class="nq-section-sub">
      Compare three response modes side-by-side: baseline, RAG-grounded, and guardrail-enforced
    </div>
    """, unsafe_allow_html=True)

    # ── Query input ──
    st.markdown('<div class="nq-query-box">', unsafe_allow_html=True)
    st.markdown('<div class="nq-query-label">🔍 Your Question</div>', unsafe_allow_html=True)

    with st.form(key="chat_form"):
        question = st.text_input(
            "question",
            placeholder="e.g., What are the key features and specifications of this product?",
            label_visibility="collapsed",
            key="chat_input",
        )
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            submit = st.form_submit_button("🚀  Send Query", use_container_width=True)
        with c2:
            st.markdown(f'<div style="font-size:0.75rem;color:#64748b;padding-top:0.6rem;">Model: <span style="color:#4f8ef7;">{st.session_state.get("model_id","—")}</span></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div style="font-size:0.75rem;color:#64748b;padding-top:0.6rem;">Top-K: <span style="color:#10b981;">{st.session_state.get("top_k",5)}</span></div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if "last_question" not in st.session_state:
        st.session_state["last_question"] = None

    # ── Response columns ──
    if submit:
        if not question or not question.strip():
            st.warning("Please enter a question before sending.")
        elif question.strip() == st.session_state.get("last_question"):
            st.info("Same question detected — modify it or clear to re-run.")
        else:
            st.session_state["last_question"] = question.strip()
            results = {"without": None, "with": None, "guard": None}

            col_a, col_b, col_c = st.columns(3, gap="medium")

            # ── Column A: Without Context ──
            with col_a:
                st.markdown("""
                <div class="nq-response-card nq-rc-blue">
                  <div class="nq-response-header">
                    <div class="nq-response-dot" style="background:#4f8ef7;box-shadow:0 0 6px #4f8ef7;"></div>
                    <div class="nq-response-title">Baseline Response</div>
                    <span class="nq-response-badge nq-rb-blue">No RAG</span>
                  </div>
                """, unsafe_allow_html=True)
                with st.spinner("Generating…"):
                    try:
                        ans_a, t_a = generate_response_without_context(
                            question,
                            st.session_state["model_id"],
                            st.session_state["client"],
                            st.session_state["provider"],
                        )
                        st.markdown(f'<div class="nq-response-body">{ans_a}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="nq-response-footer">⏱ {t_a:.2f}s · Model only · No document context</div>', unsafe_allow_html=True)
                        results["without"] = {"answer": ans_a, "time": t_a}
                    except Exception as e:
                        st.error(f"Error: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Column B: With Context ──
            with col_b:
                st.markdown("""
                <div class="nq-response-card nq-rc-green">
                  <div class="nq-response-header">
                    <div class="nq-response-dot" style="background:#10b981;box-shadow:0 0 6px #10b981;"></div>
                    <div class="nq-response-title">RAG-Grounded Response</div>
                    <span class="nq-response-badge nq-rb-green">With Context</span>
                  </div>
                """, unsafe_allow_html=True)
                with st.spinner("Searching & generating…"):
                    try:
                        t_search0 = time.time()
                        _ec, _ep = _get_embed_client_and_provider()
                        chunks, q_emb = search_similar_chunks(
                            question, _ec,
                            st.session_state["top_k"],
                            st.session_state["min_similarity"],
                            st.session_state["embedding_type"],
                            _ep,
                        )
                        t_search = time.time() - t_search0

                        sims_str = ", ".join(f"{c['similarity']:.2f}" for c in chunks)
                        st.markdown(f'<div style="font-size:0.72rem;color:#10b981;margin-bottom:0.6rem;">🔍 {len(chunks)} chunks retrieved · similarities: [{sims_str}]</div>', unsafe_allow_html=True)

                        ans_b, t_b = generate_response_with_context(
                            question, chunks,
                            st.session_state["model_id"],
                            st.session_state["client"],
                            st.session_state["provider"],
                        )
                        st.markdown(f'<div class="nq-response-body">{ans_b}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="nq-response-footer">⏱ {t_b+t_search:.2f}s · Search {t_search:.2f}s · {len(chunks)} chunks used</div>', unsafe_allow_html=True)
                        results["with"] = {"answer": ans_b, "time": t_b + t_search, "search_time": t_search, "chunks": chunks}
                    except Exception as e:
                        st.error(f"Error: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Column C: Guardrail ──
            with col_c:
                st.markdown("""
                <div class="nq-response-card nq-rc-amber">
                  <div class="nq-response-header">
                    <div class="nq-response-dot" style="background:#f59e0b;box-shadow:0 0 6px #f59e0b;"></div>
                    <div class="nq-response-title">Guardrail Response</div>
                    <span class="nq-response-badge nq-rb-amber">Context-Only</span>
                  </div>
                """, unsafe_allow_html=True)
                with st.spinner("Applying guardrails…"):
                    try:
                        guard_chunks = (results.get("with") or {}).get("chunks") or []
                        if not guard_chunks:
                            guard_chunks, _ = search_similar_chunks(
                                question, _get_embed_client_and_provider()[0],
                                st.session_state["top_k"],
                                st.session_state["min_similarity"],
                                st.session_state["embedding_type"],
                                _get_embed_client_and_provider()[1],
                            )
                        ans_c, t_c = generate_response_with_guardrail(
                            question, guard_chunks,
                            st.session_state["model_id"],
                            st.session_state["client"],
                            st.session_state["provider"],
                        )
                        st.markdown(f'<div class="nq-response-body">{ans_c}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="nq-response-footer">⏱ {t_c:.2f}s · Strict context enforcement · No hallucination</div>', unsafe_allow_html=True)
                        results["guard"] = {"answer": ans_c, "time": t_c, "chunks": guard_chunks}
                    except Exception as e:
                        st.error(f"Error: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

            # ── Retrieved Context Panel ──
            all_chunks = (results.get("with") or {}).get("chunks", [])
            if all_chunks:
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📚  View Retrieved Context  ·  {len(all_chunks)} chunks  ·  search {results['with']['search_time']:.2f}s", expanded=False):
                    for i, c in enumerate(all_chunks, start=1):
                        meta    = c.get("metadata", {})
                        src     = meta.get("source_filename") or meta.get("filename") or "—"
                        product = meta.get("product") or meta.get("product_name") or "—"
                        preview = c["content"][:400].replace("\n", " ")
                        sim_pct = int(c["similarity"] * 100)
                        st.markdown(f"""
                        <div class="nq-chunk-card">
                          <div class="nq-chunk-header">
                            <span class="nq-chunk-num">Chunk {i}</span>
                            <span class="nq-chunk-sim">▲ {c['similarity']:.3f}</span>
                            <span class="nq-chunk-src">{src} · {product}</span>
                          </div>
                          <div class="nq-sim-bar-wrap">
                            <div class="nq-sim-bar-bg">
                              <div class="nq-sim-bar-fill" style="width:{sim_pct}%;"></div>
                            </div>
                            <span style="font-size:0.68rem;color:#64748b;">{sim_pct}%</span>
                          </div>
                          <div class="nq-chunk-text" style="margin-top:0.6rem;">{preview}{"…" if len(c["content"])>400 else ""}</div>
                        </div>
                        """, unsafe_allow_html=True)

    else:
        # Empty state
        st.markdown("""
        <div class="nq-empty-state" style="padding:4rem 1rem;">
          <div class="nq-empty-icon">🧬</div>
          <div class="nq-empty-title">Ready to answer your questions</div>
          <div class="nq-empty-desc">
            Type a question above and click <strong>Send Query</strong> to see<br>
            three AI response modes compared side-by-side
          </div>
          <div style="margin-top:1.5rem;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
            <span class="nq-badge nq-badge-blue">🔵 Baseline</span>
            <span class="nq-badge nq-badge-green">🟢 RAG-Grounded</span>
            <span class="nq-badge nq-badge-amber" style="color:#f59e0b;border-color:rgba(245,158,11,0.35);background:rgba(245,158,11,0.08);">🟡 Guardrail</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
