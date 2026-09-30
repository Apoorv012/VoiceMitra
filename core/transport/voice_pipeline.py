"""Voice Transport: a WebRTC room (LiveKit or Daily) with Sarvam STT and TTS at its edges.

The agent core stays text-in/text-out (see base.py). This class hides a Pipecat pipeline:

    room input -> Sarvam STT -> _Bridge -> Sarvam TTS -> room output

`_Bridge` swallows final transcripts into a queue (`receive_text`) and tracks whether the bot is
mid-speech; `send_text` queues a TTSSpeakFrame. Nothing in core/agent or domains/ imports Pipecat.
Which room provider carries the audio is the subclass's business (livekit_transport.py,
daily_transport.py).
"""

from __future__ import annotations

import asyncio
import logging

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    EndFrame,
    Frame,
    TranscriptionFrame,
    TTSSpeakFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import BaseTransport

from core.providers.stt import get_stt_service
from core.providers.tts import get_tts_service
from core.transport.base import Transport

log = logging.getLogger(__name__)

# How long the agent waits for the patient to enter the room after the call is placed.
JOIN_TIMEOUT_SECONDS = 120
# Upper bound on waiting for the last spoken line to finish before hanging up.
SPEECH_DRAIN_TIMEOUT_SECONDS = 60


class _Bridge(FrameProcessor):
    def __init__(self, owner: "VoiceTransport") -> None:
        super().__init__()
        self._owner = owner

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                self._owner._on_transcript(text)
            return  # final transcripts go to the agent, not on to TTS
        if isinstance(frame, BotStartedSpeakingFrame):
            self._owner._speaking.set()
            self._owner._idle.clear()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._owner._speaking.clear()
            self._owner._idle.set()
        await self.push_frame(frame, direction)


class VoiceTransport(Transport):
    def __init__(
        self, room: BaseTransport, *, joined_events: tuple[str, ...], left_events: tuple[str, ...]
    ) -> None:
        self._inbox: asyncio.Queue[str | None] = asyncio.Queue()
        self._joined = asyncio.Event()
        self._speaking = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self.ended = False

        self._room = room
        self._task = PipelineTask(
            Pipeline([room.input(), get_stt_service(), _Bridge(self), get_tts_service(), room.output()]),
            params=PipelineParams(allow_interruptions=False),
        )
        self._runner_task: asyncio.Task | None = None

        async def on_joined(*_args) -> None:
            self._joined.set()

        async def on_left(*_args) -> None:
            self._inbox.put_nowait(None)  # patient hung up: unblocks receive_text

        for name in joined_events:
            room.add_event_handler(name, on_joined)
        for name in left_events:
            room.add_event_handler(name, on_left)

    async def start(self) -> None:
        self._runner_task = asyncio.create_task(PipelineRunner(handle_sigint=False).run(self._task))
        try:
            await asyncio.wait_for(self._joined.wait(), JOIN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await self.end()
            raise

    async def send_text(self, text: str) -> None:
        self._idle.clear()  # speech is pending until the output transport reports it finished
        await self._task.queue_frame(TTSSpeakFrame(text))

    async def receive_text(self) -> str | None:
        if self.ended:
            return None
        return await self._inbox.get()

    async def end(self) -> None:
        if self.ended:
            return
        self.ended = True
        try:
            await asyncio.wait_for(self._idle.wait(), SPEECH_DRAIN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            log.warning("gave up waiting for the closing line to finish")
        await self._task.queue_frame(EndFrame())
        if self._runner_task is not None:
            await asyncio.gather(self._runner_task, return_exceptions=True)

    async def abort(self) -> None:
        """Drop out immediately (operator ended the call), without waiting for speech to finish."""
        self.ended = True
        await self._task.cancel()
        if self._runner_task is not None:
            await asyncio.gather(self._runner_task, return_exceptions=True)

    def _on_transcript(self, text: str) -> None:
        if not self.ended:
            self._inbox.put_nowait(text)
