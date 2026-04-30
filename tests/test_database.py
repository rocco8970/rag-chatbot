#!/usr/bin/env python3
"""Test DB schema and pgvector functionality for the RAG chatbot.

Checks performed:
- Connect using credentials from .env
- Verify tables: company_documents, document_chunks, conversations
- Verify pgvector extension is enabled
- Verify HNSW index exists on document_chunks.embedding (or fallback ivfflat)
- Test vector operations using a temporary table
- Print a summary report

Run: python tests/test_database.py
"""

import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def load_config():
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "admin"),
        "user": os.getenv("DB_USER", "admin"),
        "password": os.getenv("DB_PASSWORD", ""),
    }


def connect(cfg):
    conn_str = (
        f"host={cfg['host']} port={cfg['port']} dbname={cfg['dbname']} "
        f"user={cfg['user']} password={cfg['password']}"
    )
    try:
        conn = psycopg2.connect(conn_str)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        print(f"ERROR: Unable to connect to DB: {e}")
        sys.exit(1)


def check_tables(conn):
    expected = {"company_documents", "document_chunks", "conversations"}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
            tables = {r[0] for r in cur.fetchall()}
        found = expected & tables
        missing = expected - tables
        return found, missing
    except Exception as e:
        print(f"ERROR checking tables: {e}")
        raise


def check_pgvector(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            return cur.fetchone() is not None
    except Exception as e:
        print(f"ERROR checking pgvector extension: {e}")
        raise


def check_hnsw_index(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'document_chunks';")
            idxs = cur.fetchall()
        if not idxs:
            return False, []
        names = [r[0] for r in idxs]
        defs = [r[1].lower() for r in idxs]
        # Look for hnsw first
        for name, definition in zip(names, defs):
            if 'using hnsw' in definition:
                return True, [(name, 'hnsw')]
        # fallback: ivfflat
        for name, definition in zip(names, defs):
            if 'using ivfflat' in definition:
                return True, [(name, 'ivfflat')]
        return False, list(zip(names, ['unknown'] * len(names)))
    except Exception as e:
        print(f"ERROR checking indexes: {e}")
        raise


def test_vector_ops(conn):
    """Create a temp table with a small-dimension vector column and test distance ops."""
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute("CREATE TEMP TABLE tmp_vec (id SERIAL PRIMARY KEY, v vector(3));")
            cur.execute("INSERT INTO tmp_vec (v) VALUES ('[1,1,1]');")
            cur.execute("SELECT v <-> '[1,1,1]'::vector(3) as dist FROM tmp_vec LIMIT 1;")
            row = cur.fetchone()
            if row is None:
                return False, 'no result'
            dist = row[0]
            # Expect distance 0 for identical vectors
            ok = abs(float(dist) - 0.0) < 1e-6
            return ok, float(dist)
    except Exception as e:
        return False, str(e)


def main():
    cfg = load_config()
    print("Connecting using:")
    print(f" host={cfg['host']} port={cfg['port']} dbname={cfg['dbname']} user={cfg['user']}")

    conn = connect(cfg)
    summary = {
        'connected': True,
        'tables_found': [],
        'tables_missing': [],
        'pgvector_enabled': False,
        'hnsw_index': False,
        'hnsw_details': [],
        'vector_test': (False, None),
    }

    try:
        found, missing = check_tables(conn)
        summary['tables_found'] = sorted(found)
        summary['tables_missing'] = sorted(missing)

        summary['pgvector_enabled'] = check_pgvector(conn)

        hnsw_ok, hnsw_details = check_hnsw_index(conn)
        summary['hnsw_index'] = hnsw_ok
        summary['hnsw_details'] = hnsw_details

        vec_ok, vec_info = test_vector_ops(conn)
        summary['vector_test'] = (vec_ok, vec_info)

    except Exception as e:
        print(f"Test encountered an error: {e}")
    finally:
        conn.close()

    # Print summary report
    print('\n==== DATABASE TEST SUMMARY ====')
    print(f"Connected: {summary['connected']}")
    print(f"Tables found: {summary['tables_found']}")
    print(f"Tables missing: {summary['tables_missing']}")
    print(f"pgvector extension enabled: {summary['pgvector_enabled']}")
    print(f"HNSW/IVF index present: {summary['hnsw_index']}")
    if summary['hnsw_details']:
        for nm, typ in summary['hnsw_details']:
            print(f" - index: {nm}, type: {typ}")
    print(f"Vector operation test (identical vectors distance == 0): {summary['vector_test'][0]} -> {summary['vector_test'][1]}")

    # Determine overall success
    ok = summary['connected'] and not summary['tables_missing'] and summary['pgvector_enabled'] and summary['vector_test'][0]
    if ok:
        print("\nALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("\nONE OR MORE CHECKS FAILED")
        sys.exit(2)


if __name__ == '__main__':
    main()
