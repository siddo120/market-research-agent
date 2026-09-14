"""Thin async wrapper around the Anthropic (Claude) Messages API.

Everything the agent asks the model to do goes through `chat_json`, which asks
for a JSON object and parses it out of the reply.

Notes specific to current Claude models (Opus 5 / Sonnet 5 …):
- There is no OpenAI-style `response_format=json_object`, so we instruct JSON in
  the prompt (the system prompts already do) and extract it robustly.
- `temperature` and the other sampling params are rejected (HTTP 400) on these
  models, so we do NOT send them — the `temperature` arg is kept for call-site
  compatibility but ignored.
- Adaptive thinking is on by default; the reply is a list of content blocks
  (thinking + text). We concatenate only the text blocks before parsing.
"""
import json
import re
from anthropic import AsyncAnthropic

from . import config

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the model's text, tolerating code fences/prose."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back to the outermost { ... } span.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return {"_parse_error": True, "_raw": text[:2000]}


async def chat_json(system: str, user: str, temperature: float = 0.2) -> dict:
    """Call Claude and return parsed JSON. `temperature` is ignored (see module doc)."""
    resp = await _get_client().messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=16000,
        output_config={"effort": config.ANTHROPIC_EFFORT},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text")
    return _extract_json(text)
