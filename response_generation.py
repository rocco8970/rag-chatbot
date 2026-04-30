"""Response generation utilities supporting OpenAI and AWS Bedrock.

Provides three functions:
- generate_response_without_context
- generate_response_with_context
- generate_response_with_guardrail

Each function returns a tuple: (answer: str, response_time: float)

Provider handling:
- `provider="OpenAI"` expects a client from `from openai import OpenAI`
- `provider="Bedrock"` expects a boto3-style client with `invoke_model` method

Note: Bedrock APIs vary; this module attempts a generic `invoke_model` call
which works with typical boto3 Bedrock clients. Adjust if your Bedrock SDK
requires different parameters.
"""

from typing import List, Dict, Tuple, Union
import time
import json
import sys

from openai import OpenAI
from openai import OpenAIError

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except Exception:
    boto3 = None


ContextChunk = Union[str, Dict]


_WITH_CONTEXT_TEMPLATE = (
    "You are provided with {N} context passages. Read ALL of them carefully and synthesize information to answer comprehensively.\n\n"
    "IMPORTANT: Use information from ALL context passages, not just one. Combine and synthesize.\n\n"
    "{contexts}\n\n"
    "Question: {question}\n\n"
    "Instructions:\n"
    "- Read and analyze ALL {N} passages\n"
    "- Combine information from multiple passages\n"
    "- Provide comprehensive answer\n"
    "- Extract specific details (counts, lists, etc.)\n\n"
    "Answer:"
)


_GUARDRAIL_TEMPLATE = (
    "You are provided with {N} context passages. Answer based ONLY on this information.\n\n"
    "STRICT RULES:\n"
    "1. Read ALL {N} passages\n"
    "2. Answer ONLY using information in contexts\n"
    "3. You MAY synthesize and infer from passages\n"
    "4. You MAY count, list, enumerate items mentioned\n"
    "5. If contexts have relevant info, use it (can be partial)\n"
    "6. ONLY say 'I don't have information' if NO relevant info at all\n"
    "7. Do NOT use external knowledge\n\n"
    "{contexts}\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


def _build_context_block(context_chunks: List[ContextChunk]) -> str:
    parts: List[str] = []
    for i, c in enumerate(context_chunks, start=1):
        if isinstance(c, dict):
            content = c.get("content") or c.get("text") or str(c)
        else:
            content = str(c)
        parts.append(f"[Context {i}]\n{content}")
    return "\n\n".join(parts)


def _call_openai_chat(client: OpenAI, messages: List[Dict], model: str, temperature: float = 0.7) -> str:
    try:
        resp = client.chat.completions.create(model=model, messages=messages, temperature=temperature)
        # SDK returns choices with message
        choices = getattr(resp, "choices", None)
        if not choices:
            # try dict-like
            choices = resp.get("choices") if isinstance(resp, dict) else None
        if choices and len(choices) > 0:
            msg = choices[0].get("message") if isinstance(choices[0], dict) else getattr(choices[0], "message", None)
            if isinstance(msg, dict):
                return msg.get("content", "").strip()
            return getattr(msg, "content", "").strip()
        return ""
    except OpenAIError as e:
        raise RuntimeError(f"OpenAI API error: {e}")
    except Exception as e:
        raise RuntimeError(f"OpenAI call failed: {e}")


def _call_bedrock_invoke(client, model: str, prompt: str, temperature: float = 0.7) -> str:
    if client is None:
        raise RuntimeError("Bedrock client not available (boto3 not installed)")
    # Generic invocation for boto3 Bedrock client
    try:
        invoke_args = {
            "modelId": model,
            "contentType": "application/json",
            "accept": "application/json",
            "body": json.dumps({"input": prompt}).encode("utf-8"),
        }
        resp = client.invoke_model(**invoke_args)
        # resp['body'] is a streaming HTTP response; try reading
        body = resp.get("body")
        if hasattr(body, "read"):
            raw = body.read()
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
        else:
            raw = body

        # The exact shape depends on model; try to parse JSON
        try:
            parsed = json.loads(raw)
            # try known keys
            if "output" in parsed:
                return parsed["output"].strip()
            # some returns: {"body": {"text": "..."}}
            if isinstance(parsed, dict):
                # flatten
                for v in parsed.values():
                    if isinstance(v, str) and v.strip():
                        return v.strip()
            return str(parsed).strip()
        except Exception:
            return str(raw).strip()
    except (BotoCoreError, ClientError) as e:
        raise RuntimeError(f"Bedrock invocation error: {e}")
    except Exception as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def generate_response_without_context(
    question: str,
    model: str,
    client,
    provider: str = "OpenAI",
    temperature: float = 0.7,
) -> Tuple[str, float]:
    """Generate a response without external context.

    Supports OpenAI and AWS Bedrock providers.

    Returns:
        (answer, response_time_seconds)
    """
    start = time.perf_counter()
    try:
        if provider.lower() == "openai":
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question},
            ]
            answer = _call_openai_chat(client, messages, model=model, temperature=temperature)
        elif provider.lower() in ("bedrock", "aws", "awsbedrock"):
            prompt = question
            answer = _call_bedrock_invoke(client, model, prompt, temperature=temperature)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    except Exception as e:
        print(f"generate_response_without_context error: {e}", file=sys.stderr)
        return "", 0.0
    finally:
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
    """Generate a response that synthesizes information from provided context passages.

    Combines all context chunks into numbered passages and instructs the LLM to
    use information from all passages.
    """
    start = time.perf_counter()
    try:
        N = len(context_chunks)
        contexts = _build_context_block(context_chunks)
        prompt = _WITH_CONTEXT_TEMPLATE.format(N=N, contexts=contexts, question=question)

        if provider.lower() == "openai":
            messages = [
                {"role": "system", "content": "You are a helpful assistant that answers using provided contexts."},
                {"role": "user", "content": prompt},
            ]
            answer = _call_openai_chat(client, messages, model=model, temperature=temperature)
        elif provider.lower() in ("bedrock", "aws", "awsbedrock"):
            answer = _call_bedrock_invoke(client, model, prompt, temperature=temperature)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    except Exception as e:
        print(f"generate_response_with_context error: {e}", file=sys.stderr)
        return "", 0.0
    finally:
        elapsed = time.perf_counter() - start

    return answer, elapsed


def generate_response_with_guardrail(
    question: str,
    context_chunks: List[ContextChunk],
    model: str,
    client,
    provider: str = "OpenAI",
) -> Tuple[str, float]:
    """Generate a guarded response using only provided context.

    Rules: prohibit use of external knowledge; allow synthesis and inference;
    lower temperature for focused answers.
    """
    start = time.perf_counter()
    try:
        N = len(context_chunks)
        contexts = _build_context_block(context_chunks)
        prompt = _GUARDRAIL_TEMPLATE.format(N=N, contexts=contexts, question=question)

        temperature = 0.3
        if provider.lower() == "openai":
            messages = [
                {"role": "system", "content": "You are a helpful assistant that must only use the provided context passages."},
                {"role": "user", "content": prompt},
            ]
            answer = _call_openai_chat(client, messages, model=model, temperature=temperature)
        elif provider.lower() in ("bedrock", "aws", "awsbedrock"):
            answer = _call_bedrock_invoke(client, model, prompt, temperature=temperature)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    except Exception as e:
        print(f"generate_response_with_guardrail error: {e}", file=sys.stderr)
        return "", 0.0
    finally:
        elapsed = time.perf_counter() - start

    return answer, elapsed
