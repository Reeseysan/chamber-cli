import json
import pytest
import httpx
import respx

OLLAMA_BASE = "http://localhost:11434"
LMSTUDIO_BASE = "http://localhost:1234"


def make_chat_completion_chunk(content: str, finish: bool = False):
    """Build an OpenAI-compatible SSE chat completion chunk."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if not finish else {},
                "finish_reason": "stop" if finish else None,
            }
        ],
    }


def make_chat_completion_response(content: str):
    """Build an OpenAI-compatible non-streaming chat completion response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


def build_sse_stream(chunks: list[dict]) -> str:
    """Build an SSE stream string from chunk dicts."""
    lines = []
    for chunk in chunks:
        lines.append(f"data: {json.dumps(chunk)}\n\n")
    lines.append("data: [DONE]\n\n")
    return "".join(lines)
