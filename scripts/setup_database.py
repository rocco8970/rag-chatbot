#!/usr/bin/env python3
"""Create and verify database schema for the RAG chatbot.

This script:
- Loads DB config from environment via python-dotenv
- Connects using psycopg2 with AUTOCOMMIT
- Creates the `vector` extension (pgvector)
- Drops and creates tables: company_documents, document_chunks, conversations
- Creates indexes (HNSW on embeddings and B-tree indexes)
- Grants privileges to the `admin` role
- Verifies table and extension creation

Run as a user that can connect as a superuser (or use sudo -u postgres to run this script).
"""

import os
import sys
import textwrap
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


def load_config():
    load_dotenv()
    cfg = {
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "dbname": os.getenv("DB_NAME", "postgres"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    return cfg


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
        print(f"ERROR: could not connect to database: {e}")
        sys.exit(1)


def exec_sql(conn, statement, params=None, desc=None):
    if desc:
        print(desc)
    try:
        with conn.cursor() as cur:
            cur.execute(statement, params or ())
    except Exception as e:
        print(f"ERROR executing SQL ({desc or 'statement'}): {e}")
        raise


def main():
    print("Loading configuration from environment...")
    cfg = load_config()

    print("Connecting to database...")
    conn = connect(cfg)

    try:
        # Ensure pgvector extension exists before creating vector columns
        print("Creating pgvector extension if not exists...")
        exec_sql(conn, "CREATE EXTENSION IF NOT EXISTS vector;",
                 desc="Create vector extension")

        # Drop tables if they exist (development convenience)
        print("Dropping existing tables (if any)...")
        drop_sql = textwrap.dedent("""
            DROP TABLE IF EXISTS conversations CASCADE;
            DROP TABLE IF EXISTS document_chunks CASCADE;
            DROP TABLE IF EXISTS company_documents CASCADE;
        """)
        exec_sql(conn, drop_sql, desc="Drop existing tables")

        # Create company_documents
        print("Creating table: company_documents")
        create_company_documents = textwrap.dedent("""
            CREATE TABLE company_documents (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                file_type VARCHAR(50),
                file_path TEXT,
                total_chunks INTEGER DEFAULT 0,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB
            );
        """)
        exec_sql(conn, create_company_documents, desc="Create company_documents")

        # Create document_chunks
        print("Creating table: document_chunks")
        create_document_chunks = textwrap.dedent("""
            CREATE TABLE document_chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES company_documents(id) ON DELETE CASCADE,
                chunk_index INTEGER NOT NULL,
                filename VARCHAR(255),
                product_name VARCHAR(100),
                content TEXT NOT NULL,
                content_length INTEGER,
                embedding vector(1536),
                chunk_metadata JSONB,
                embedding_type VARCHAR(20) DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(document_id, chunk_index)
            );
        """)
        exec_sql(conn, create_document_chunks, desc="Create document_chunks")

        # Create conversations
        print("Creating table: conversations")
        create_conversations = textwrap.dedent("""
            CREATE TABLE conversations (
                id SERIAL PRIMARY KEY,
                session_id UUID NOT NULL,
                user_question TEXT NOT NULL,
                bot_response TEXT,
                chunks_used INTEGER[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        exec_sql(conn, create_conversations, desc="Create conversations")

        # Indexes: HNSW on embedding and B-tree indexes
        print("Creating HNSW index on document_chunks.embedding (vector)")
        # Use cosine metric for embeddings (vector_cosine_ops); tune m/ef_construction as needed
        create_hnsw_index = textwrap.dedent("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 200);
        """)
        try:
            exec_sql(conn, create_hnsw_index, desc="Create HNSW index")
        except Exception:
            print("Warning: HNSW index creation failed. Ensure pgvector version supports HNSW or try ivfflat.")
            # fallback to ivfflat
            fallback_ivf = textwrap.dedent("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_ivfflat
                ON document_chunks
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
            exec_sql(conn, fallback_ivf, desc="Create IVFFLAT index (fallback)")

        # B-tree indexes for fast lookup
        print("Creating B-tree indexes...")
        exec_sql(conn, "CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id);",
                 desc="Index document_id")
        exec_sql(conn, "CREATE INDEX IF NOT EXISTS idx_document_chunks_product_name ON document_chunks(product_name);",
                 desc="Index product_name")
        exec_sql(conn, "CREATE INDEX IF NOT EXISTS idx_document_chunks_filename ON document_chunks(filename);",
                 desc="Index filename")
        exec_sql(conn, "CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id);",
                 desc="Index session_id")

        # Grant privileges to admin user
        admin_user = os.getenv("DB_ADMIN_USER", "admin")
        print(f"Granting privileges to user '{admin_user}'...")
        grant_sql = sql.SQL("""
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {admin};
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {admin};
        """).format(admin=sql.Identifier(admin_user))
        exec_sql(conn, grant_sql.as_string(conn), desc="Grant privileges to admin")

        # Optionally change owner of tables to admin
        try:
            owner_sql = sql.SQL("ALTER TABLE company_documents OWNER TO {admin}; ALTER TABLE document_chunks OWNER TO {admin}; ALTER TABLE conversations OWNER TO {admin};").format(admin=sql.Identifier(admin_user))
            exec_sql(conn, owner_sql.as_string(conn), desc="Change table owners to admin")
        except Exception:
            print("Warning: could not change table owner (you may not have permission). Continuing...")

        # Verification: check extension and tables
        print("Verifying extension and table creation...")
        with conn.cursor() as cur:
            cur.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
            ext = cur.fetchone()
            if ext:
                print(f"Extension found: {ext[0]}")
            else:
                print("Warning: pgvector extension not found in this cluster.")

            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
            tables = [r[0] for r in cur.fetchall()]
            expected = {'company_documents', 'document_chunks', 'conversations'}
            missing = expected - set(tables)
            if missing:
                print(f"ERROR: Missing tables: {missing}")
                sys.exit(2)
            else:
                print("All expected tables exist: ", sorted(tables))

            # Check indexes (document_chunks embedding index)
            cur.execute("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'document_chunks';")
            idxs = cur.fetchall()
            print("document_chunks indexes:")
            for name, definition in idxs:
                print(" - ", name)

        print("Database schema setup completed successfully.")

    finally:
        conn.close()


if __name__ == '__main__':
    main()
