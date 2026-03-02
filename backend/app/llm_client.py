"""Unified LLM client wrapping OpenAI and Anthropic."""
from __future__ import annotations
from typing import Optional
from .config import settings


MessageList = list[dict[str, str]]


class LLMClient:
    def generate(
        self,
        messages: MessageList,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        p = provider or settings.llm_provider
        m = model or settings.active_model

        if p == "openai":
            return self._openai(messages, m, temperature, max_tokens)
        elif p == "anthropic":
            return self._anthropic(messages, m, temperature, max_tokens)
        elif p == "gemini":
            return self._gemini(messages, m, temperature, max_tokens)
        else:
            raise ValueError(
                f"Unknown provider '{p}'. Configure LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY."
            )

    # ── OpenAI ─────────────────────────────────────────────────────────────────

    def _openai(
        self, messages: MessageList, model: str, temperature: float, max_tokens: int
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    # ── Anthropic ──────────────────────────────────────────────────────────────

    def _anthropic(
        self, messages: MessageList, model: str, temperature: float, max_tokens: int
    ) -> str:
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)

        # Split out system message (Anthropic uses a separate top-level param)
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]
        system_text = "\n\n".join(system_parts) if system_parts else None

        kwargs: dict = dict(
            model=model,
            messages=non_system,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_text:
            kwargs["system"] = system_text

        response = client.messages.create(**kwargs)
        return response.content[0].text  # type: ignore[union-attr]

    # ── Gemini ─────────────────────────────────────────────────────────────────

    def _gemini(
        self, messages: MessageList, model: str, temperature: float, max_tokens: int
    ) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        # Split system prompt; Gemini uses a separate system_instruction param
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        non_system = [m for m in messages if m["role"] != "system"]
        system_text = "\n\n".join(system_parts) if system_parts else None

        contents = [
            types.Content(role=m["role"], parts=[types.Part(text=m["content"])])
            for m in non_system
        ]

        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system_text,
        )

        response = client.models.generate_content(
            model=model, contents=contents, config=config
        )
        return response.text or ""


llm_client = LLMClient()
