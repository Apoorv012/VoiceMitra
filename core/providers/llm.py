"""LLM client factories. Both Sarvam and Gemini expose OpenAI-compatible chat-completions
endpoints (same request/response schema, `tools`/function-calling included), so
core/agent/runtime.py only ever depends on the generic AsyncOpenAI client shape -- swapping which
provider actually answers is a one-line change in whichever entrypoint builds AgentConfig, nothing
in runtime/policy/tools/guardrails needs to change.

Sarvam: confirmed against https://docs.sarvam.ai/api-reference/chat/chat-completions.
Gemini: confirmed against https://ai.google.dev/gemini-api/docs/openai.

Chunk 3's voice pipeline still uses Sarvam specifically for STT/TTS (best Hindi/Hinglish
quality) regardless of which LLM provider is used for chat-completions here.
"""

from __future__ import annotations

import os

from openai import AsyncOpenAI

SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
SARVAM_DEFAULT_MODEL = "sarvam-105b-conversations"  # tuned for real-time conversational/voice-agent use

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Flash-Lite over plain Flash: ~500 free requests/day vs ~20 for Flash tier (confirmed via
# ai.google.dev/gemini-api/docs/rate-limits, Sept 2026) -- a single test conversation burns
# 5-8 requests, so Flash's daily quota exhausts almost immediately during iterative testing.
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash-lite"

# Backwards-compatible aliases (Chunk 2 code imports these names directly).
DEFAULT_MODEL = SARVAM_DEFAULT_MODEL


def get_sarvam_llm_client() -> AsyncOpenAI:
    api_key = os.environ["SARVAM_API_KEY"]
    return AsyncOpenAI(api_key=api_key, base_url=SARVAM_BASE_URL)


def get_gemini_llm_client() -> AsyncOpenAI:
    api_key = os.environ["GEMINI_API_KEY"]
    return AsyncOpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)


def get_llm_client_and_model() -> tuple[AsyncOpenAI, str]:
    """Picks a provider based on LLM_PROVIDER env var ("sarvam" default, or "gemini"), and an
    optional LLM_MODEL override. Used by bot.py so the provider is a config switch, not a code
    change."""
    provider = os.environ.get("LLM_PROVIDER", "sarvam").lower()
    if provider == "gemini":
        return get_gemini_llm_client(), os.environ.get("LLM_MODEL", GEMINI_DEFAULT_MODEL)
    return get_sarvam_llm_client(), os.environ.get("LLM_MODEL", SARVAM_DEFAULT_MODEL)
