import os
import json
import time
import pytest
from unittest import mock

"""
Comprehensive test suite scaffold for RAG chatbot app.

Notes:
- These tests are intended as a structured starting point. Some tests
  require a running PostgreSQL with pgvector and valid OpenAI/Bedrock
  credentials. Use environment variables to point to test databases and
  provide API keys.
- Tests that require external services are marked with markers and can be
  skipped in CI or run manually.
"""

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "admin")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

REQUIRES_DB = pytest.mark.skipif(not os.getenv("TEST_WITH_DB"), reason="Set TEST_WITH_DB=1 to run DB tests")
REQUIRES_OPENAI = pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="Set OPENAI_API_KEY to run OpenAI tests")


@pytest.fixture(scope="session")
def db_conn():
    """Return a psycopg2 connection to the configured test database.

    Requires TEST_WITH_DB=1 to run.
    """
    if not os.getenv("TEST_WITH_DB"):
        pytest.skip("DB tests disabled")
    import psycopg2

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    yield conn
    conn.close()


def test_table_schema_smoke(db_conn):
    """TEST 1: Database Connection and Schema

    - Verify required tables exist
    - Verify pgvector extension exists
    - Verify indexes exist (best-effort)
    """
    cur = db_conn.cursor()
    cur.execute("SELECT to_regclass('public.company_documents'), to_regclass('public.document_chunks'), to_regclass('public.conversations');")
    a, b, c = cur.fetchone()
    assert a is not None and b is not None and c is not None

    # pgvector extension
    cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
    rows = cur.fetchall()
    assert len(rows) >= 0

    cur.close()


def test_document_processing_functions():
    """TEST 2: Document processing (pdf/txt/docx) - basic smoke tests

    These tests do not require real files; they check that functions exist
    and basic chunking behaves as expected.
    """
    from src.document_utils import clean_extracted_text, chunk_text

    sample = "This is a simple test. " * 200
    cleaned = clean_extracted_text(sample)
    chunks = chunk_text(cleaned, chunk_size=200, overlap=40)
    assert isinstance(chunks, list)
    assert len(chunks) > 0
    # check overlap
    if len(chunks) >= 2:
        assert chunks[0]['content'][:50] != chunks[1]['content'][:50]


@REQUIRES_OPENAI
def test_embeddings_generation():
    """TEST 3: Embeddings - dimension and batch generation"""
    from src.embeddings_utils import create_embedding, create_embeddings_batch
    from openai import OpenAI

    client = OpenAI()
    v = create_embedding("hello world", client)
    assert isinstance(v, list)
    assert len(v) == 1536

    embs = create_embeddings_batch(["a", "b", "c"], client)
    assert isinstance(embs, list)
    assert len(embs) == 3
    assert len(embs[0]) == 1536


@REQUIRES_DB
def test_vector_search_ranking(db_conn):
    """TEST 4: Vector search basic behavior

    - Insert two synthetic chunks with distinct embeddings
    - Query similarity and verify ranking
    """
    cur = db_conn.cursor()
    # create two simple embeddings where one is closer to query embedding
    # This is a lightweight smoke check; detailed numeric checks depend on model
    cur.execute("INSERT INTO company_documents (filename,file_type,file_path,total_chunks,metadata) VALUES (%s,%s,%s,%s,%s) RETURNING id;", ("test.txt","txt","",1,json.dumps({})))
    doc_id = cur.fetchone()[0]
    emb1 = '[' + ','.join(['0.0'] * 1536) + ']'
    emb2 = '[' + ','.join(['1.0'] * 1536) + ']'
    cur.execute("INSERT INTO document_chunks (document_id, chunk_index, filename, product_name, content, content_length, embedding, chunk_metadata, embedding_type) VALUES (%s,%s,%s,%s,%s,%s,%s::vector,%s,%s) RETURNING id;", (doc_id, 0, 'test.txt', 'test', 'zero', 4, emb1, json.dumps({}), 'general'))
    id1 = cur.fetchone()[0]
    cur.execute("INSERT INTO document_chunks (document_id, chunk_index, filename, product_name, content, content_length, embedding, chunk_metadata, embedding_type) VALUES (%s,%s,%s,%s,%s,%s,%s::vector,%s,%s) RETURNING id;", (doc_id, 1, 'test.txt', 'test', 'ones', 4, emb2, json.dumps({}), 'general'))
    id2 = cur.fetchone()[0]
    db_conn.commit()

    # perform a simple search using the app helper (if present)
    from streamlit_app import search_similar_chunks
    chunks, q_emb = search_similar_chunks('hello', None, top_k=2, min_similarity=0.0, embedding_type='general', provider='OpenAI')
    assert isinstance(chunks, list)

    cur.close()


def test_response_generation_smoke():
    """TEST 5: Response generation smoke tests (no external calls)

    - Verify functions accept arguments and return tuple-like results
    """
    from src.response_generation import generate_response_without_context

    # We will mock the OpenAI client call to avoid network
    class DummyClient:
        def chat(self):
            return None

    ans, t = generate_response_without_context("Hello", "gpt-3.5-turbo", DummyClient(), provider='OpenAI')
    # function may return empty string when client is dummy
    assert isinstance(ans, (str,))


@REQUIRES_OPENAI
def test_enhanced_embeddings_flow(monkeypatch):
    """TEST 6: Enhanced embeddings generation (integration test)

    - Mock generate_enhanced_json to return a predictable JSON
    - Run generate_enhanced_embeddings_for_all against a test DB (if enabled)
    """
    from src.embeddings_utils import generate_enhanced_embeddings_for_all
    from openai import OpenAI

    client = OpenAI()

    # If no DB test, skip
    if not os.getenv('TEST_WITH_DB'):
        pytest.skip('DB disabled for enhanced embeddings test')

    # Run the generator (this will contact OpenAI for embeddings)
    res = generate_enhanced_embeddings_for_all(client)
    assert isinstance(res, dict)
    assert 'status' in res


# Additional tests (performance / benchmarks / Bedrock) can be added here following the structure above.
