import json

import httpx

import config


class LlamaServerUnavailable(Exception):
    """Raised when llama-server can't be reached at all (down, refused, timed out)."""


async def health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{config.LLAMA_SERVER_URL}/health")
            return r.status_code == 200
    except httpx.HTTPError:
        return False


async def tokenize(text: str) -> int:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{config.LLAMA_SERVER_URL}/tokenize", json={"content": text})
            r.raise_for_status()
            return len(r.json()["tokens"])
    except httpx.HTTPError as e:
        raise LlamaServerUnavailable("llama-server is unreachable") from e


def chat_completion(messages: list[dict], sampling_params: dict, stream: bool = False, timeout: float = 120.0):
    """Non-streaming: awaitable resolving to {"content": str, "reasoning": str}.
    Streaming (stream=True): async generator yielding {"type": "content"|"reasoning", "text": str} chunks.
    `reasoning` comes from llama-server's `reasoning_content` field (see --reasoning-format), populated
    automatically for models whose chat template supports thinking; empty otherwise.
    `timeout` only applies to non-streaming calls - callers with no UX deadline (e.g. background
    summarization) should pass a longer value, since the single llama-server slot may be busy."""
    payload = {"messages": messages, "stream": stream, **sampling_params}
    if stream:
        return _stream_chat_completion(payload)
    return _chat_completion_once(payload, timeout)


async def _chat_completion_once(payload: dict, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(f"{config.LLAMA_SERVER_URL}/v1/chat/completions", json=payload)
            r.raise_for_status()
            message = r.json()["choices"][0]["message"]
            return {"content": message.get("content") or "", "reasoning": message.get("reasoning_content") or ""}
    except httpx.HTTPError as e:
        raise LlamaServerUnavailable("llama-server is unreachable") from e


async def _stream_chat_completion(payload: dict):
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{config.LLAMA_SERVER_URL}/v1/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]" or not data_str:
                        continue
                    delta = json.loads(data_str)["choices"][0]["delta"]
                    if delta.get("reasoning_content"):
                        yield {"type": "reasoning", "text": delta["reasoning_content"]}
                    if delta.get("content"):
                        yield {"type": "content", "text": delta["content"]}
    except httpx.HTTPError as e:
        raise LlamaServerUnavailable("llama-server is unreachable") from e
