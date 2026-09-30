"""Text-to-speech provider factory (Sarvam Bulbul, via Pipecat). The agent writes Hinglish in Roman
script; Bulbul reads that with hi-IN. Voice/language are overridable via SARVAM_TTS_VOICE /
SARVAM_TTS_LANGUAGE."""

from __future__ import annotations

import os

from pipecat.services.sarvam.tts import SarvamTTSService


def get_tts_service() -> SarvamTTSService:
    return SarvamTTSService(
        api_key=os.environ["SARVAM_API_KEY"],
        settings=SarvamTTSService.Settings(
            voice=os.environ.get("SARVAM_TTS_VOICE", "ritu"),
            language=os.environ.get("SARVAM_TTS_LANGUAGE", "hi-IN"),
        ),
    )
