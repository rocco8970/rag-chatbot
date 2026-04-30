"""Embedding helper functions using OpenAI SDK.

Provides:
- create_embeddings_batch(texts, client) -> List[List[float]]
- create_embedding(text, client) -> List[float]

Requires `openai>=1.0.0` style client (from `openai import OpenAI`).
The client will use the `OPENAI_API_KEY` environment variable when created
via `OpenAI()` unless you pass a configured client instance.
"""

from typing import List
import time
import random
import sys

from openai import OpenAI
from openai import OpenAIError
import os
import json
import logging
import psycopg2
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def _extract_embeddings_from_response(resp) -> List[List[float]]:
    """Normalize embedding extraction from SDK response object."""
    embeddings: List[List[float]] = []
    # resp.data is expected to be iterable with embedding in .embedding or ['embedding']
    for item in getattr(resp, "data", []) or []:
        emb = None
        # try attribute access
        if hasattr(item, "embedding"):
            emb = getattr(item, "embedding")
        elif isinstance(item, dict):
            emb = item.get("embedding")

        if emb is None:
            raise ValueError("No embedding returned for one of the inputs")

        embeddings.append(list(emb))

    return embeddings


def create_embeddings_batch(texts: List[str], client: OpenAI, *, model: str = "text-embedding-3-small") -> List[List[float]]:
    """Create embeddings for a batch of texts using OpenAI.

    Args:
        texts: List of text strings to embed.
        client: An instance of `openai.OpenAI` (configured with API key).
        model: Embedding model to use (defaults to `text-embedding-3-small`).

    Returns:
        A list of embeddings; each embedding is a list of floats (length 1536).

    Behavior:
    - Retries up to 3 times on API errors with exponential backoff.
    - Prints progress messages to stdout.
    - Raises ValueError for invalid input.
    """
    if not texts:
        return []

    if not isinstance(texts, list):
        raise ValueError("texts must be a list of strings")

    max_retries = 3
    backoff_base = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[embeddings] Requesting embeddings for {len(texts)} texts (attempt {attempt})...")
            resp = client.embeddings.create(model=model, input=texts)
            embeddings = _extract_embeddings_from_response(resp)
            print(f"[embeddings] Received {len(embeddings)} embeddings.")
            return embeddings
        except OpenAIError as e:
            # API-level errors
            print(f"[embeddings] OpenAI API error on attempt {attempt}: {e}", file=sys.stderr)
            if attempt == max_retries:
                raise
        except Exception as e:
            # Unexpected errors
            print(f"[embeddings] Unexpected error on attempt {attempt}: {e}", file=sys.stderr)
            if attempt == max_retries:
                raise

        # Exponential backoff with jitter
        sleep_for = backoff_base * (2 ** (attempt - 1))
        sleep_for = sleep_for + random.uniform(0, 0.5 * sleep_for)
        print(f"[embeddings] Waiting {sleep_for:.1f}s before retry...")
        time.sleep(sleep_for)

    # Should not reach here
    return []


def create_embedding(text: str, client: OpenAI, *, model: str = "text-embedding-3-small") -> List[float]:
    """Create a single embedding for `text` using OpenAI.

    Args:
        text: Input text to embed.
        client: An instance of `openai.OpenAI`.
        model: Embedding model name.

    Returns:
        A single embedding vector (list of floats).

    Notes:
    - Uses the same retry/backoff strategy as the batch function.
    """
    if text is None:
        raise ValueError("text must not be None")

    # Reuse batch function by passing single-element list
    embeddings = create_embeddings_batch([text], client, model=model)
    if not embeddings:
        raise RuntimeError("No embedding returned for the input text")
    return embeddings[0]


def generate_enhanced_json(product_name: str, chunk_content: str, client: OpenAI, *, model: str = "gpt-4o-mini") -> str:
    """Call a chat model to produce a fully-dynamic JSON tagging object for a text chunk.

    Returns the raw JSON string. Raises RuntimeError on failure.
    """
    if chunk_content is None:
        raise ValueError("chunk_content must not be None")

    prompt = (
        "You are a tagging and structuring engine.\n\n"
        f"Product Name: {product_name}\n"
        f"Content Chunk: {chunk_content}\n\n"
        "Output FULLY DYNAMIC JSON with ONLY fields that have actual data.\n\n"
        "Suggested fields (use if info exists, ADD MORE if needed):\n"
        "- product_name, specification, current_voltage, power\n"
        "- features, applications, standards, tags\n"
        "- model_number, manufacturer, dimensions, weight\n"
        "- operating_temperature, certifications, compatibility\n\n"
        "RULES:\n"
        "- ONLY include fields with actual information\n"
        "- CREATE NEW FIELDS if you find relevant info\n"
        "- Do NOT include null values - omit the field\n"
        "- Use snake_case for field names\n"
        "- Always include original_text\n"
        "- Output JSON only, no markdown\n\n"
        "Output:"
    )

    messages = [
        {"role": "system", "content": "You are a tagging and structuring engine."},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0)
    except Exception as e:
        logger.exception("OpenAI chat call failed for enhanced JSON generation")
        raise RuntimeError(f"OpenAI call failed: {e}")

    # Extract text content from SDK response
    content = ""
    try:
        choices = getattr(resp, "choices", None) or (resp.get("choices") if isinstance(resp, dict) else None)
        if choices and len(choices) > 0:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
            if isinstance(msg, dict):
                content = msg.get("content", "").strip()
            else:
                content = getattr(msg, "content", "").strip()
        else:
            # fallback: try raw text
            content = str(resp)
    except Exception:
        content = str(resp)

    # strip markdown code fences if present
    if content.startswith("```"):
        parts = content.split("\n", 1)
        # try to remove leading ```json or ```
        content = content.strip().lstrip("`")

    # attempt to extract JSON object from text
    json_text = content
    try:
        # quick parse: if valid JSON, return pretty compact string
        obj = json.loads(json_text)
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        # try to extract first {...} block
        import re

        m = re.search(r"(\{[\s\S]*\})", json_text)
        if m:
            candidate = m.group(1)
            try:
                obj = json.loads(candidate)
                return json.dumps(obj, ensure_ascii=False)
            except Exception:
                pass

    # If we couldn't parse JSON, raise an error with original content for diagnosis
    logger.error("Failed to parse JSON from model output: %s", content[:500])
    raise RuntimeError("Model did not return valid JSON for enhanced JSON generation")


def generate_enhanced_embeddings_for_all(client: OpenAI, progress_callback=None) -> Dict:
    """Generate enhanced JSON for all chunks with embedding_type='general' and insert enhanced rows.

    Returns dict with status and count. Continues on per-chunk errors.
    """
    # DB config from env (defaults mirror streamlit_app.py)
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "5432"))
    DB_NAME = os.getenv("DB_NAME", "admin")
    DB_USER = os.getenv("DB_USER", "admin")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = False

    result = {"status": "unknown", "count": 0, "errors": []}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding_type = 'enhanced';")
            enhanced_count = int(cur.fetchone()[0])
        if enhanced_count > 0:
            result.update({"status": "exists", "count": enhanced_count})
            return result

        # fetch general chunks
        with conn.cursor() as cur:
            cur.execute("SELECT id, document_id, chunk_index, filename, product_name, content FROM document_chunks WHERE embedding_type = 'general' ORDER BY id;")
            rows = cur.fetchall()

        total = len(rows)
        inserted = 0

        for idx, row in enumerate(rows):
            row_id, document_id, chunk_index, filename, product_name, content = row
            try:
                enhanced_json = generate_enhanced_json(product_name or "", content, client)
            except Exception as e:
                msg = f"Failed to generate enhanced JSON for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx + 1, "total": total, "status": "error", "message": msg})
                continue

            # create embedding for enhanced JSON
            try:
                emb = create_embedding(enhanced_json, client)
            except Exception as e:
                msg = f"Failed to create embedding for enhanced JSON for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx + 1, "total": total, "status": "error", "message": msg})
                continue

            # insert new row with embedding_type='enhanced'
            try:
                with conn.cursor() as cur:
                    pg_vec = "[" + ",".join(str(float(x)) for x in emb) + "]"
                    insert_sql = (
                        "INSERT INTO document_chunks (document_id, chunk_index, filename, product_name, content, content_length, embedding, chunk_metadata, embedding_type)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s::vector, %s, %s) RETURNING id;"
                    )
                    chunk_meta = json.dumps({"source_chunk_id": row_id})
                    cur.execute(insert_sql, (document_id, chunk_index, filename, product_name, enhanced_json, len(enhanced_json), pg_vec, chunk_meta, 'enhanced'))
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    inserted += 1
                    if progress_callback:
                        progress_callback({"current": idx + 1, "total": total, "status": "ok", "last_id": new_id})
            except Exception as e:
                conn.rollback()
                msg = f"DB insert failed for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx + 1, "total": total, "status": "error", "message": msg})
                continue

        result.update({"status": "success", "count": inserted})
        return result
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    # Simple demonstration (requires OPENAI_API_KEY set in env)
    try:
        client = OpenAI()
    except Exception as e:
        print(f"Failed to create OpenAI client: {e}")
        raise

    sample_texts = ["Hello world", "OpenAI embeddings test"]
    embs = create_embeddings_batch(sample_texts, client)
    print(f"Generated {len(embs)} embeddings; first length: {len(embs[0]) if embs else 0}")
