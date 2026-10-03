"""
Pluggable LLM interface for Stage 2 (plan generation) and Stage 3 (evidence).

Every stage calls through `LLM`. Two implementations:

* `APILLM`  -- a real model behind any OpenAI-compatible endpoint (Groq, Ollama,
               Together, OpenRouter, ...). Configure it with a `.env` file in the
               repo root and build it with `APILLM.from_env()`:

                   LLM_BASE_URL=https://api.groq.com/openai/v1
                   LLM_API_KEY=gsk_...
                   LLM_MODEL=qwen/qwen3.8-27b

               For a local Ollama model instead:
                   LLM_BASE_URL=http://localhost:11434/v1
                   LLM_API_KEY=ollama
                   LLM_MODEL=qwen3:8b

* `DemoLLM` -- canned answers so the offline demo and tests run with no key.

`.env` is git-ignored: each person uses their own key. See `.env.example`.
"""
from __future__ import annotations

import json
import os
import re
import time
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the model's raw text completion for a prompt."""


class LLMConfigError(RuntimeError):
    pass


class APILLM(LLM):
    """Real model via an OpenAI-compatible chat-completions endpoint."""

    def __init__(self, base_url: str, api_key: str, model: str,
                 max_retries: int = 5, timeout: float = 60.0):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self.model = model
        self.max_retries = max_retries

    @classmethod
    def from_env(cls, env_file: str | None = None) -> "APILLM":
        """Build from LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (read from .env if present)."""
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file or _default_env_path(), override=False)
        except ImportError:
            pass  # fall back to whatever is already in the environment
        missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.getenv(k)]
        if missing:
            raise LLMConfigError(
                f"Missing {', '.join(missing)}. Copy .env.example to .env and fill it in."
            )
        return cls(os.environ["LLM_BASE_URL"], os.environ["LLM_API_KEY"], os.environ["LLM_MODEL"])

    def complete(self, prompt: str) -> str:
        from openai import RateLimitError, APIConnectionError, APITimeoutError, InternalServerError
        delay = 2.0
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                return resp.choices[0].message.content or ""
            except (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError):
                # Free tiers rate-limit: back off and retry instead of crashing a long eval run.
                if attempt == self.max_retries:
                    raise
                time.sleep(delay)
                delay = min(delay * 2, 60.0)
        raise AssertionError("unreachable")


def _default_env_path() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", ".env")


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict:
    """
    Pull the JSON object out of a real model's reply.

    Real models rarely return bare JSON: reasoning models (Qwen3 etc.) prepend a
    <think>...</think> block, and most wrap output in ```json fences or add a
    sentence before/after. This strips those and parses the first {...} object.
    """
    cleaned = _THINK_RE.sub("", text).strip()
    fenced = _FENCE_RE.search(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    if start == -1:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
    obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    return obj


class DemoLLM(LLM):
    """
    Deterministic stand-in used ONLY for the offline architecture demo and tests,
    so the pipeline runs with no API key and no network. It matches known demo
    questions to hand-verified outputs and does not generalize -- use APILLM
    (`python -m src.demo.run_demo --live`) for real questions.
    """

    def __init__(self, canned_responses: dict[str, str]):
        self.canned = canned_responses

    def complete(self, prompt: str) -> str:
        for key, response in self.canned.items():
            if key in prompt:
                return response
        raise NotImplementedError(
            "DemoLLM has no canned response for this prompt. "
            "This is expected -- swap in APILLM for real questions."
        )
