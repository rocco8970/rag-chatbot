"""Response generation — OpenAI and AWS Bedrock (Claude via Messages API).

Provides:
- generate_response_without_context(question, model, client, provider)
- generate_response_with_context(question, chunks, model, client, provider)
- generate_response_with_guardrail(question, chunks, model, client, provider)

Each returns (answer: str, elapsed_seconds: float).

Bedrock note:
  Claude models use the Bedrock Messages API (anthropic_version bedrock-2023-05-31).
  The model ID must be a full Bedrock ARN or the short cross-region inference ID,
  e.g. "anthropic.claude-3-haiku-20240307-v1:0".
"""

from typing import List, Dict, Tuple, Union
import time
import json
import sys

from openai import OpenAI, OpenAIError

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None

ContextChunk = Union[str, Dict]

_WITH_CONTEXT_TEMPLATE = (
    "You are provided with {N} context passages. Read ALL of them carefully and synthesize "
    "information to answer comprehensively.\n\n"
    "IMPORTANT: Use information from ALL context passages, not just one. Combine and synthesize.\n\n"
    "{contexts}\n\n"
    "Question: {question}\n\n"
    "Instructions:\n"
    "- Read and analyze ALL {N} passages\n"
    "- Combine information from multiple passages\n"
    "- Provide a comprehensive answer\n"
    "- Extract specific details (counts, lists, specs, etc.)\n\n"
    "Answer:"
)

_GUARDRAIL_TEMPLATE = (
    "You are provided with {N} context passages. Answer based ONLY on this information.\n\n"
    "STRICT RULES:\n"
    "1. Read ALL {N} passages\n"
    "2. Answer ONLY using information in the contexts\n"
    "3. You MAY synthesize and infer from passages\n"
    "4. You MAY count, list, enumerate items mentioned\n"
    "5. If contexts have relevant info, use it\n"
    "6. ONLY say 'I don't have information' if NO relevant info exists at all\n"
    "7. Do NOT use external knowledge\n\n"
    "{contexts}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


def _build_context_block(chunks: List[ContextChunk]) -> str:
    parts = []
    for i, c in enumerate(chunks, start=1):
        content = c.get("content") or c.get("text") or str(c) if isinstance(c, dict) else str(c)
        parts.append(f"[Context {i}]\n{content}")
    return "\n\n".join(parts)


# ── OpenAI ───────────────────────────────────────────────────────────────────

def _call_openai(client: OpenAI, messages: List[Dict], model: str, temperature: float) -> str:
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
        choices = getattr(resp, "choices", None) or (resp.get("choices") if isinstance(resp, dict) else None)
        if choices:
            msg = getattr(choices[0], "message", None) or (choices[0].get("message") if isinstance(choices[0], dict) else None)
            if isinstance(msg, dict):
                return msg.get("content", "").strip()
            return getattr(msg, "content", "").strip()
        return ""
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}")
    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e}")


# ── AWS Bedrock (Claude Messages API) ────────────────────────────────────────

def _call_bedrock_claude(client, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Invoke a Claude model on Bedrock using the Messages API format."""
    if client is None:
        raise RuntimeError("Bedrock client is None — check AWS credentials in .env")

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "temperature": temperature,
        "messages": [
            {"role": "user", "content": user_prompt},
        ],
    }
    if system_prompt:
        body["system"] = system_prompt

    try:
        resp = client.invoke_model(
            modelId=model,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        raw = json.loads(resp["body"].read())
        # Claude Messages API returns: {"content": [{"type": "text", "text": "..."}], ...}
        content_blocks = raw.get("content", [])
        if content_blocks and isinstance(content_blocks, list):
            return content_blocks[0].get("text", "").strip()
        # Fallback
        return str(raw).strip()
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Bedrock invocation error: {e}")
    except Exception as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def _dispatch(provider: str, client, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
    """Route to the correct backend."""
    p = provider.lower()
    if p == "openai":
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        return _call_openai(client, messages, model, temperature)
    elif p in ("bedrock", "aws", "awsbedrock", "aws bedrock"):
        return _call_bedrock_claude(client, model, system_prompt, user_prompt, temperature)
    else:
        raise ValueError(f"Unsupported provider: {provider!r}. Use 'OpenAI' or 'AWS Bedrock'.")


# ── Public functions ──────────────────────────────────────────────────────────

def generate_response_without_context(
    question: str,
    model: str,
    client,
    provider: str = "OpenAI",
    temperature: float = 0.7,
) -> Tuple[str, float]:
    start = time.perf_counter()
    answer = ""
    try:
        answer = _dispatch(
            provider, client, model,
            system_prompt="You are a helpful assistant.",
            user_prompt=question,
            temperature=temperature,
        )
    except Exception as e:
        print(f"generate_response_without_context error: {e}", file=sys.stderr)
        answer = f"⚠️ Error: {e}"
    elapsed = time.perf_counter() - start
    return answer, elapsed


def generate_response_with_context(
    question: str,
    context_chunks: List[ContextChunk],
    model: str,
    client,
    provider: str = "OpenAI",
    temperature: float = 0.7,
) -> Tuple[str, float]:
    start = time.perf_counter()
    answer = ""
    try:
        N = len(context_chunks)
        contexts = _build_context_block(context_chunks)
        user_prompt = _WITH_CONTEXT_TEMPLATE.format(N=N, contexts=contexts, question=question)
        answer = _dispatch(
            provider, client, model,
            system_prompt="You are a helpful assistant that answers using provided contexts.",
            user_prompt=user_prompt,
            temperature=temperature,
        )
    except Exception as e:
        print(f"generate_response_with_context error: {e}", file=sys.stderr)
        answer = f"⚠️ Error: {e}"
    elapsed = time.perf_counter() - start
    return answer, elapsed


def generate_response_with_guardrail(
    question: str,
    context_chunks: List[ContextChunk],
    model: str,
    client,
    provider: str = "OpenAI",
) -> Tuple[str, float]:
    start = time.perf_counter()
    answer = ""
    try:
        N = len(context_chunks)
        contexts = _build_context_block(context_chunks)
        user_prompt = _GUARDRAIL_TEMPLATE.format(N=N, contexts=contexts, question=question)
        answer = _dispatch(
            provider, client, model,
            system_prompt="You are a strict assistant that must only use the provided context passages. Do not use external knowledge.",
            user_prompt=user_prompt,
            temperature=0.3,
        )
    except Exception as e:
        print(f"generate_response_with_guardrail error: {e}", file=sys.stderr)
        answer = f"⚠️ Error: {e}"
    elapsed = time.perf_counter() - start
    return answer, elapsed
