"""
Pluggable LLM interface for Stage 2 (plan generation) and Stage 3 (evidence).

LLM is the interface every stage calls through. Swap DemoLLM for a real
implementation (OpenRouterLLM / TogetherLLM / etc.) once you have an API key
for one of IndicDB's benchmarked models (Qwen3-8B, Llama 3.3, DeepSeek V3.2,
MiniMax M2.7) -- nothing else in the pipeline needs to change.
"""
from __future__ import annotations
from abc import ABC, abstractmethod


class LLM(ABC):
    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return the model's raw text completion for a prompt."""


class APILLM(LLM):
    """Real implementation, OpenAI-compatible endpoint (Together AI, Groq, Fireworks, OpenRouter all work).

    Usage:
        llm = APILLM(base_url="https://api.together.xyz/v1", api_key=..., model="Qwen/Qwen3-8B")
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def complete(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return resp.choices[0].message.content


class DemoLLM(LLM):
    """
    Deterministic stand-in used ONLY for this offline architecture demo, so the
    pipeline is runnable with no API key and no network access. It matches a
    small set of known demo questions to hand-verified outputs so the FULL
    pipeline (retrieval -> plan -> SQL -> execution -> scoring) can be proven
    end-to-end. It does not generalize to new questions -- replace with
    APILLM before running against real IndicDB tasks.
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
