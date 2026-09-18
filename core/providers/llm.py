"""Sarvam chat-completions client, used via the OpenAI SDK since Sarvam's API is OpenAI-compatible
(same request/response schema, including `tools`/function-calling and streaming) -- confirmed
against https://docs.sarvam.ai/api-reference/chat/chat-completions.
"""

from __future__ import annotations

import os

from openai import AsyncOpenAI

SARVAM_BASE_URL = "https://api.sarvam.ai/v1"
DEFAULT_MODEL = "sarvam-105b-conversations"  # tuned for real-time conversational/voice-agent use


def get_sarvam_llm_client() -> AsyncOpenAI:
    api_key = os.environ["SARVAM_API_KEY"]
    return AsyncOpenAI(api_key=api_key, base_url=SARVAM_BASE_URL)
