"""The per-speaker audio filter must route mic audio by participant identity (`user_id`).

Regression: filtering on `frame.id` (Pipecat's numeric frame counter) dropped every mic frame, so the
agent greeted but never heard the patient.
"""

import asyncio

from pipecat.frames.frames import InputAudioRawFrame, TextFrame, UserAudioRawFrame

from core.transport.voice_pipeline import _audio_from

_PCM = b"\0\0" * 160


def _user_audio(user_id: str) -> UserAudioRawFrame:
    return UserAudioRawFrame(audio=_PCM, sample_rate=16000, num_channels=1, user_id=user_id)


def test_keeps_only_the_named_speakers_audio():
    keep = _audio_from("patient")
    assert asyncio.run(keep(_user_audio("patient")))
    assert not asyncio.run(keep(_user_audio("doctor")))
    assert not asyncio.run(keep(InputAudioRawFrame(audio=_PCM, sample_rate=16000, num_channels=1)))


def test_passes_non_audio_frames_through():
    assert asyncio.run(_audio_from("patient")(TextFrame(text="hi")))
