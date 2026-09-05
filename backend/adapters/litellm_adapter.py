"""Model adapters: direct Ollama HTTP (preferred for local) + lazy litellm for APIs."""
from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from backend.types import GenerationResult, ModelConfig

# Soften SSL issues in restricted corporate/dev environments for optional remote fetches
os.environ.setdefault("SSL_CERT_FILE", os.environ.get("SSL_CERT_FILE", ""))
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("REQUESTS_CA_BUNDLE", "")


def _approx_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


class ModelAdapter:
    def __init__(self, config: ModelConfig, temperature: float = 0.7):
        self.config = config
        self.temperature = temperature
        self._use_ollama = config.local or config.litellm_model.startswith("ollama/")

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> GenerationResult:
        if max_tokens <= 0:
            return GenerationResult(
                content="",
                completion_tokens=0,
                prompt_tokens=0,
                truncated=True,
                finish_reason="budget_exhausted",
            )
        if self._use_ollama:
            return self._generate_ollama(messages, max_tokens, seed=seed, stop=stop)
        return self._generate_litellm(messages, max_tokens, seed=seed, stop=stop)

    def _ollama_model_name(self) -> str:
        name = self.config.litellm_model
        if name.startswith("ollama/"):
            name = name[len("ollama/") :]
        return name

    def _generate_ollama(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> GenerationResult:
        base = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        payload: dict[str, Any] = {
            "model": self._ollama_model_name(),
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens,
            },
        }
        if seed is not None:
            payload["options"]["seed"] = seed
        if stop:
            payload["options"]["stop"] = stop

        with httpx.Client(timeout=300.0) as client:
            resp = client.post(f"{base.rstrip('/')}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

        content = (data.get("message") or {}).get("content") or ""
        # Ollama reports eval_count (completion) and prompt_eval_count
        completion_tokens = int(data.get("eval_count") or _approx_tokens(content))
        prompt_tokens = int(
            data.get("prompt_eval_count")
            or _approx_tokens("".join(m.get("content", "") for m in messages))
        )
        done_reason = data.get("done_reason") or data.get("finish_reason")
        truncated = done_reason in ("length", "max_tokens") or (
            completion_tokens >= max_tokens and done_reason not in ("stop", None)
        )
        return GenerationResult(
            content=content,
            completion_tokens=completion_tokens,
            prompt_tokens=prompt_tokens,
            truncated=truncated,
            finish_reason=str(done_reason) if done_reason else None,
            raw=data,
        )

    def _generate_litellm(
        self,
        messages: list[dict[str, str]],
        max_tokens: int,
        seed: int | None = None,
        stop: list[str] | None = None,
    ) -> GenerationResult:
        # Lazy import — avoids tiktoken SSL failures when only using Ollama
        try:
            import litellm
            from litellm import completion

            litellm.drop_params = True
            litellm.suppress_debug_info = True
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                f"litellm unavailable ({e}). For local models use ollama/ prefix."
            ) from e

        kwargs: dict[str, Any] = {
            "model": self.config.litellm_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": self.temperature,
        }
        if seed is not None:
            kwargs["seed"] = seed
        if stop:
            kwargs["stop"] = stop

        resp = completion(**kwargs)
        choice = resp.choices[0]
        content = choice.message.content or ""
        finish = getattr(choice, "finish_reason", None)
        usage = getattr(resp, "usage", None)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        if completion_tokens == 0 and content:
            completion_tokens = _approx_tokens(content)
        if prompt_tokens == 0:
            prompt_tokens = _approx_tokens("".join(m.get("content", "") for m in messages))
        truncated = finish in ("length", "max_tokens")
        return GenerationResult(
            content=content,
            completion_tokens=completion_tokens,
            prompt_tokens=prompt_tokens,
            truncated=truncated,
            finish_reason=str(finish) if finish else None,
            raw=resp,
        )

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (
            prompt_tokens / 1000.0 * self.config.cost_per_1k_prompt
            + completion_tokens / 1000.0 * self.config.cost_per_1k_completion
        )
