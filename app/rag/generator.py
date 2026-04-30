from __future__ import annotations

from abc import ABC, abstractmethod
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        raise NotImplementedError

    @abstractmethod
    async def stream_generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> AsyncIterator[dict[str, str]]:
        raise NotImplementedError


class OllamaLLMProvider(LLMProvider):
    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature},
                },
            )
            response.raise_for_status()
        payload = response.json()
        return payload.get("message", {}).get("content", "")

    async def stream_generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> AsyncIterator[dict[str, str]]:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    content = payload.get("message", {}).get("content", "")
                    if content:
                        yield {"type": "answer", "text": content}


class OpenAICompatibleLLMProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    async def generate(self, messages: list[dict[str, str]], temperature: float = 0.2) -> str:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        _apply_cloud_llm_options(payload)
        url = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    async def stream_generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
    ) -> AsyncIterator[dict[str, str]]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        _apply_cloud_llm_options(payload)
        url = (
            self.base_url
            if self.base_url.endswith("/chat/completions")
            else f"{self.base_url}/chat/completions"
        )
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    for reasoning_text in _reasoning_texts(delta):
                        yield {"type": "reasoning", "text": reasoning_text}
                    content = delta.get("content") or ""
                    if content:
                        yield {"type": "answer", "text": content}


def get_llm_provider() -> LLMProvider:
    backend = settings.llm_backend.lower()
    if backend == "ollama":
        return OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_llm_model,
        )
    if backend in {"openai", "openai_compatible", "cloud"}:
        return OpenAICompatibleLLMProvider(
            base_url=settings.cloud_llm_base_url,
            api_key=settings.cloud_llm_api_key,
            model=settings.cloud_llm_model,
        )
    raise ValueError(f"Unsupported LLM backend: {settings.llm_backend}")


def _apply_cloud_llm_options(payload: dict[str, Any]) -> None:
    if settings.cloud_llm_max_tokens is not None:
        payload["max_tokens"] = settings.cloud_llm_max_tokens
    if settings.cloud_llm_top_p is not None:
        payload["top_p"] = settings.cloud_llm_top_p
    if settings.cloud_llm_enable_thinking is not None:
        payload["enable_thinking"] = settings.cloud_llm_enable_thinking
    if settings.cloud_llm_reasoning_effort:
        payload["reasoning_effort"] = settings.cloud_llm_reasoning_effort
    if payload.get("stream") and settings.cloud_llm_stream_include_usage:
        payload["stream_options"] = {"include_usage": True}


def _reasoning_texts(delta: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    reasoning_content = delta.get("reasoning_content")
    if isinstance(reasoning_content, str) and reasoning_content:
        texts.append(reasoning_content)

    reasoning_details = delta.get("reasoning_details")
    if isinstance(reasoning_details, list):
        for detail in reasoning_details:
            if isinstance(detail, dict):
                text = detail.get("text") or detail.get("content")
                if isinstance(text, str) and text:
                    texts.append(text)
            elif isinstance(detail, str) and detail:
                texts.append(detail)

    return texts
