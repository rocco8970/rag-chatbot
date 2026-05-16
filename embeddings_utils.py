"""Embedding helper functions — supports OpenAI and AWS Bedrock (Titan Embeddings v2).

Provides:
- create_embeddings_batch(texts, client, *, provider, model) -> List[List[float]]
- create_embedding(text, client, *, provider, model)         -> List[float]

provider="openai"  → uses openai.OpenAI client  (text-embedding-3-small, dim=1536)
provider="bedrock" → uses boto3 bedrock-runtime  (amazon.titan-embed-text-v2:0, dim=1536)

Both return 1536-dimensional vectors so the pgvector schema stays unchanged.
"""

from typing import List, Dict, Optional
import time
import random
import sys
import os
import json
import logging

import psycopg2

logger = logging.getLogger(__name__)

# ── Bedrock Titan Embeddings model ──────────────────────────────────────────
BEDROCK_EMBED_MODEL = "amazon.titan-embed-text-v2:0"   # 1536-dim, same as OpenAI small


# ────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────

def _embed_openai(texts: List[str], client, model: str) -> List[List[float]]:
    """Call OpenAI embeddings API."""
    try:
        from openai import OpenAIError
    except ImportError:
        raise RuntimeError("openai package not installed")

    max_retries = 3
    backoff_base = 1.0

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[embeddings/openai] {len(texts)} texts (attempt {attempt})...")
            resp = client.embeddings.create(model=model, input=texts)
            embeddings: List[List[float]] = []
            for item in getattr(resp, "data", []) or []:
                emb = getattr(item, "embedding", None) or (item.get("embedding") if isinstance(item, dict) else None)
                if emb is None:
                    raise ValueError("No embedding in response item")
                embeddings.append(list(emb))
            print(f"[embeddings/openai] Received {len(embeddings)} embeddings.")
            return embeddings
        except Exception as e:
            print(f"[embeddings/openai] Error attempt {attempt}: {e}", file=sys.stderr)
            if attempt == max_retries:
                raise
        sleep_for = backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
        print(f"[embeddings/openai] Retrying in {sleep_for:.1f}s...")
        time.sleep(sleep_for)

    return []


def _embed_bedrock_single(text: str, client, model: str) -> List[float]:
    """Call Bedrock Titan Embeddings for a single text. Returns 1536-dim vector."""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1536,
        "normalize": True,
    })
    try:
        resp = client.invoke_model(
            modelId=model,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        raw = resp["body"].read()
        parsed = json.loads(raw)
        emb = parsed.get("embedding")
        if emb is None:
            raise ValueError(f"No 'embedding' key in Bedrock response: {list(parsed.keys())}")
        return list(emb)
    except Exception as e:
        raise RuntimeError(f"Bedrock embedding failed: {e}")


def _embed_bedrock_batch(texts: List[str], client, model: str) -> List[List[float]]:
    """Bedrock Titan does not support batch — call one-by-one with retry."""
    results = []
    for i, text in enumerate(texts):
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                print(f"[embeddings/bedrock] text {i+1}/{len(texts)} (attempt {attempt})...")
                emb = _embed_bedrock_single(text, client, model)
                results.append(emb)
                break
            except Exception as e:
                print(f"[embeddings/bedrock] Error: {e}", file=sys.stderr)
                if attempt == max_retries:
                    raise
                time.sleep(1.5 * attempt)
    return results


# ────────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────────

def create_embeddings_batch(
    texts: List[str],
    client,
    *,
    provider: str = "openai",
    model: Optional[str] = None,
) -> List[List[float]]:
    """Create embeddings for a batch of texts.

    Args:
        texts:    List of strings to embed.
        client:   openai.OpenAI instance  OR  boto3 bedrock-runtime client.
        provider: "openai" or "bedrock".
        model:    Override default model name (optional).

    Returns:
        List of 1536-dim float vectors.
    """
    if not texts:
        return []
    if not isinstance(texts, list):
        raise ValueError("texts must be a list of strings")

    p = provider.lower()
    if p == "openai":
        m = model or "text-embedding-3-small"
        return _embed_openai(texts, client, m)
    elif p in ("bedrock", "aws", "awsbedrock"):
        m = model or BEDROCK_EMBED_MODEL
        return _embed_bedrock_batch(texts, client, m)
    else:
        raise ValueError(f"Unknown embedding provider: {provider!r}. Use 'openai' or 'bedrock'.")


def create_embedding(
    text: str,
    client,
    *,
    provider: str = "openai",
    model: Optional[str] = None,
) -> List[float]:
    """Create a single embedding vector.

    Args:
        text:     Input string.
        client:   openai.OpenAI  OR  boto3 bedrock-runtime client.
        provider: "openai" or "bedrock".
        model:    Override default model (optional).

    Returns:
        1536-dim float list.
    """
    if text is None:
        raise ValueError("text must not be None")
    results = create_embeddings_batch([text], client, provider=provider, model=model)
    if not results:
        raise RuntimeError("No embedding returned")
    return results[0]


# ────────────────────────────────────────────────────────────────────────────
# Enhanced embeddings (uses same provider as caller)
# ────────────────────────────────────────────────────────────────────────────

def generate_enhanced_json(
    product_name: str,
    chunk_content: str,
    client,
    *,
    provider: str = "openai",
    model: str = "gpt-4o-mini",
) -> str:
    """Generate a structured JSON tag object for a chunk via LLM.

    Supports OpenAI chat or Bedrock Claude.
    """
    if chunk_content is None:
        raise ValueError("chunk_content must not be None")

    prompt = (
        "You are a tagging and structuring engine.\n\n"
        f"Product Name: {product_name}\n"
        f"Content Chunk: {chunk_content}\n\n"
        "Output FULLY DYNAMIC JSON with ONLY fields that have actual data.\n"
        "Suggested fields: product_name, specification, features, applications, standards, tags, model_number.\n"
        "RULES: Only include fields with real info. Use snake_case. Always include original_text. Output JSON only.\n\n"
        "Output:"
    )

    p = provider.lower()
    content = ""

    if p == "openai":
        messages = [
            {"role": "system", "content": "You are a tagging and structuring engine."},
            {"role": "user", "content": prompt},
        ]
        try:
            resp = client.chat.completions.create(model=model, messages=messages, temperature=0.0)
            choices = getattr(resp, "choices", None)
            if choices:
                msg = getattr(choices[0], "message", None)
                content = getattr(msg, "content", "").strip() if msg else ""
        except Exception as e:
            raise RuntimeError(f"OpenAI chat failed: {e}")

    elif p in ("bedrock", "aws", "awsbedrock"):
        # Use Claude via Bedrock Messages API
        bedrock_model = model if "claude" in model.lower() else "anthropic.claude-3-haiku-20240307-v1:0"
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0.0,
            "messages": [{"role": "user", "content": prompt}],
        })
        try:
            resp = client.invoke_model(
                modelId=bedrock_model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            raw = json.loads(resp["body"].read())
            content = raw.get("content", [{}])[0].get("text", "").strip()
        except Exception as e:
            raise RuntimeError(f"Bedrock chat failed: {e}")
    else:
        raise ValueError(f"Unknown provider: {provider!r}")

    # Strip markdown fences
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    # Parse JSON
    try:
        return json.dumps(json.loads(content), ensure_ascii=False)
    except Exception:
        import re
        m = re.search(r"(\{[\s\S]*\})", content)
        if m:
            try:
                return json.dumps(json.loads(m.group(1)), ensure_ascii=False)
            except Exception:
                pass
    raise RuntimeError(f"Model did not return valid JSON. Got: {content[:300]}")


def generate_enhanced_embeddings_for_all(
    client,
    *,
    provider: str = "openai",
    progress_callback=None,
) -> Dict:
    """Generate enhanced embeddings for all general chunks.

    Works with both OpenAI and Bedrock clients.
    """
    DB_HOST     = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT     = int(os.getenv("DB_PORT", "5432"))
    DB_NAME     = os.getenv("DB_NAME", "postgres")
    DB_USER     = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    conn.autocommit = False
    result = {"status": "unknown", "count": 0, "errors": []}

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding_type = 'enhanced';")
            if int(cur.fetchone()[0]) > 0:
                result.update({"status": "exists", "count": int(cur.fetchone()[0]) if False else 0})
                # re-query for accurate count
                cur.execute("SELECT COUNT(*) FROM document_chunks WHERE embedding_type = 'enhanced';")
                result["count"] = int(cur.fetchone()[0])
                result["status"] = "exists"
                return result

        with conn.cursor() as cur:
            cur.execute("SELECT id, document_id, chunk_index, filename, product_name, content FROM document_chunks WHERE embedding_type = 'general' ORDER BY id;")
            rows = cur.fetchall()

        total = len(rows)
        inserted = 0

        for idx, row in enumerate(rows):
            row_id, document_id, chunk_index, filename, product_name, content = row
            try:
                enhanced_json = generate_enhanced_json(product_name or "", content, client, provider=provider)
            except Exception as e:
                msg = f"Enhanced JSON failed for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx+1, "total": total, "status": "error", "message": msg})
                continue

            try:
                emb = create_embedding(enhanced_json, client, provider=provider)
            except Exception as e:
                msg = f"Embedding failed for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx+1, "total": total, "status": "error", "message": msg})
                continue

            try:
                with conn.cursor() as cur:
                    pg_vec = "[" + ",".join(str(float(x)) for x in emb) + "]"
                    cur.execute(
                        "INSERT INTO document_chunks (document_id, chunk_index, filename, product_name, content, content_length, embedding, chunk_metadata, embedding_type)"
                        " VALUES (%s,%s,%s,%s,%s,%s,%s::vector,%s,%s) RETURNING id;",
                        (document_id, chunk_index, filename, product_name, enhanced_json,
                         len(enhanced_json), pg_vec, json.dumps({"source_chunk_id": row_id}), "enhanced"),
                    )
                    new_id = cur.fetchone()[0]
                    conn.commit()
                    inserted += 1
                    if progress_callback:
                        progress_callback({"current": idx+1, "total": total, "status": "ok", "last_id": new_id})
            except Exception as e:
                conn.rollback()
                msg = f"DB insert failed for chunk {row_id}: {e}"
                logger.warning(msg)
                result["errors"].append(msg)
                if progress_callback:
                    progress_callback({"current": idx+1, "total": total, "status": "error", "message": msg})

        result.update({"status": "success", "count": inserted})
        return result
    finally:
        try:
            conn.close()
        except Exception:
            pass
