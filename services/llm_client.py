"""
Unified LLM client - get_client(role) pattern.

Roles (from config/models.json):
  'light' -> GPT-4o mini (90% of queries)
  'deep'  -> Claude Sonnet 4.5 (complex legal analysis)
  'async' -> Gemini Flash-Lite (background processing)

All config from config/models.json, API keys from .env.
Provider differences abstracted behind llm_call().

Usage:
    from services.llm_client import llm_call, embed, embed_batch

    result = await llm_call("light", [{"role": "user", "content": "Hello"}])
    vector = await embed("competition law")
"""
import time
import logging
from typing import Optional, List, Dict

from config import cfg

logger = logging.getLogger(__name__)

# Lazy-initialized provider clients
_clients: Dict = {}


def _init_openai():
    from openai import OpenAI
    provider_cfg = cfg.models["providers"]["openai"]
    return OpenAI(
        api_key=cfg.get_api_key(provider_cfg["env_key"]),
        base_url=provider_cfg.get("base_url"),
    )


def _init_anthropic():
    from anthropic import Anthropic
    provider_cfg = cfg.models["providers"]["anthropic"]
    return Anthropic(
        api_key=cfg.get_api_key(provider_cfg["env_key"]),
    )


def _init_google():
    from google import genai
    provider_cfg = cfg.models["providers"]["google"]
    return genai.Client(
        api_key=cfg.get_api_key(provider_cfg["env_key"]),
    )


_INIT_MAP = {
    "openai": _init_openai,
    "anthropic": _init_anthropic,
    "google": _init_google,
}


def _get_raw_client(provider: str):
    """Get or create a provider client (lazy singleton)."""
    if provider not in _clients:
        _clients[provider] = _INIT_MAP[provider]()
        logger.info(f"Initialized {provider} client")
    return _clients[provider]


# ============================================================
# Unified LLM Call
# ============================================================

async def llm_call(
    role: str,
    messages: List[Dict[str, str]],
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    response_format: Optional[str] = None,
) -> Dict:
    """
    Unified LLM call across providers.

    Args:
        role: 'light', 'deep', or 'async' (maps to config)
        messages: list of {"role": "system|user|assistant", "content": "..."}
        temperature: override config temperature
        max_tokens: override config max_tokens
        response_format: "json" for structured output, None for text

    Returns:
        {
            "content": str,
            "input_tokens": int,
            "output_tokens": int,
            "model": str,
            "provider": str,
            "latency_ms": int,
        }
    """
    role_cfg = cfg.models["roles"][role]
    provider = role_cfg["provider"]
    model = role_cfg["model"]
    temp = temperature if temperature is not None else role_cfg.get("temperature", 0.1)
    max_tok = max_tokens or role_cfg.get("max_tokens", 2000)

    client = _get_raw_client(provider)
    start = time.time()

    if provider == "openai":
        content, input_tokens, output_tokens = _call_openai(
            client, model, messages, temp, max_tok, response_format
        )
    elif provider == "anthropic":
        content, input_tokens, output_tokens = _call_anthropic(
            client, model, messages, temp, max_tok
        )
    elif provider == "google":
        content, input_tokens, output_tokens = _call_google(
            client, model, messages, temp, max_tok, response_format
        )
    else:
        raise ValueError(f"Unknown provider: {provider}")

    latency_ms = int((time.time() - start) * 1000)

    logger.info(
        f"LLM [{role}] {provider}/{model}: "
        f"{input_tokens}+{output_tokens} tokens, {latency_ms}ms"
    )

    return {
        "content": content,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "model": model,
        "provider": provider,
        "latency_ms": latency_ms,
    }


# ============================================================
# Provider-specific implementations
# ============================================================

def _call_openai(client, model, messages, temperature, max_tokens, response_format):
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    usage = response.usage
    return content, usage.prompt_tokens, usage.completion_tokens


def _call_anthropic(client, model, messages, temperature, max_tokens):
    # Anthropic handles system prompt separately
    system_msg = None
    api_messages = []
    for m in messages:
        if m["role"] == "system":
            system_msg = m["content"]
        else:
            api_messages.append({"role": m["role"], "content": m["content"]})

    kwargs = {
        "model": model,
        "messages": api_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_msg:
        kwargs["system"] = system_msg

    response = client.messages.create(**kwargs)
    content = response.content[0].text
    return content, response.usage.input_tokens, response.usage.output_tokens


def _call_google(client, model, messages, temperature, max_tokens, response_format):
    # Google genai uses different message format
    system_instruction = None
    contents = []
    for m in messages:
        if m["role"] == "system":
            system_instruction = m["content"]
        elif m["role"] == "user":
            contents.append({"role": "user", "parts": [{"text": m["content"]}]})
        elif m["role"] == "assistant":
            contents.append({"role": "model", "parts": [{"text": m["content"]}]})

    gen_config = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    if response_format == "json":
        gen_config["response_mime_type"] = "application/json"

    config_dict = {"generation_config": gen_config}
    if system_instruction:
        config_dict["system_instruction"] = system_instruction

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=config_dict,
    )
    content = response.text
    input_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
    output_tokens = getattr(response.usage_metadata, "candidates_token_count", 0)
    return content, input_tokens, output_tokens


# ============================================================
# Embedding
# ============================================================

async def embed(text: str) -> List[float]:
    """Generate embedding for a single text."""
    emb_cfg = cfg.models["embedding"]
    client = _get_raw_client(emb_cfg["provider"])

    kwargs = {
        "model": emb_cfg["model"],
        "input": text.strip(),
    }
    if "dimensions" in emb_cfg:
        kwargs["dimensions"] = emb_cfg["dimensions"]

    response = client.embeddings.create(**kwargs)
    return response.data[0].embedding


async def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""
    emb_cfg = cfg.models["embedding"]
    client = _get_raw_client(emb_cfg["provider"])

    clean_texts = [t.strip() for t in texts if t.strip()]
    if not clean_texts:
        return []

    kwargs = {
        "model": emb_cfg["model"],
        "input": clean_texts,
    }
    if "dimensions" in emb_cfg:
        kwargs["dimensions"] = emb_cfg["dimensions"]

    response = client.embeddings.create(**kwargs)
    return [item.embedding for item in response.data]
