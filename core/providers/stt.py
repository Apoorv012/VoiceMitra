"""Speech-to-text provider factory (Sarvam, via Pipecat).

Sarvam's own server-side VAD (`vad_signals=True`) decides where the patient's turns end, so no local
VAD model is needed in the pipeline. Mode "codemix" keeps English words as English inside Hindi
speech, which suits Hinglish; override with SARVAM_STT_MODE (transcribe/translit/...).
"""

from __future__ import annotations

import os

from pipecat.services.sarvam.stt import SarvamSTTService


def get_stt_service() -> SarvamSTTService:
    return SarvamSTTService(
        api_key=os.environ["SARVAM_API_KEY"],
        mode=os.environ.get("SARVAM_STT_MODE", "codemix"),
        settings=SarvamSTTService.Settings(vad_signals=True),
    )
