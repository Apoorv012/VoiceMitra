"""Voice Transport: a WebRTC room (LiveKit or Daily) with Sarvam STT and TTS at its edges.

The agent core stays text-in/text-out (see base.py). This class hides a Pipecat pipeline:

    room input -> [per-speaker: filter -> Sarvam STT -> _Bridge] -> Sarvam TTS -> room output

Each participant identity in `speakers` gets its own STT, so the transcript knows who said what once
several people share the room. `_Bridge` swallows final transcripts and hands them to the transport;
`send_text` queues a TTSSpeakFrame. Nothing in core/agent or domains/ imports Pipecat.

Who receives the transcripts depends on the mode:
  - default: the first speaker's transcripts feed `receive_text` (the agent's conversation);
  - after `set_sink(fn)`: every transcript goes to `fn(speaker, text)` instead, and the agent no longer
    hears anything -- used to put the patient on hold, then to record a merged doctor<->patient call.

Which room provider carries the audio is the subclass's business (livekit_transport.py, daily_transport.py).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InterruptionFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    TTSTextFrame,
)
from pipecat.pipeline.parallel_pipeline import ParallelPipeline
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.filters.function_filter import FunctionFilter
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.base_transport import BaseTransport
from pipecat.turns.user_turn_processor import UserTurnProcessor
from pipecat.turns.user_turn_strategies import ExternalUserTurnStrategies

from core.providers.stt import get_stt_service
from core.providers.tts import get_tts_service
from core.transport.base import Interruption, Transport

log = logging.getLogger(__name__)

# How long the agent waits for the patient to enter the room after the call is placed.
JOIN_TIMEOUT_SECONDS = 120
# Upper bound on waiting for the last spoken line to finish before hanging up.
SPEECH_DRAIN_TIMEOUT_SECONDS = 60


class _Bridge(FrameProcessor):
    def __init__(self, owner: "VoiceTransport", speaker: str) -> None:
        super().__init__()
        self._owner = owner
        self._speaker = speaker

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                self._owner._on_transcript(self._speaker, text)
            return  # final transcripts go to the transport's consumer, not on to TTS
        await self.push_frame(frame, direction)


class _SpeechTracker(FrameProcessor):
    """Last in the pipeline, after the room output: the output transport hands frames on at playback
    time, so a TTSTextFrame (one per spoken sentence) arriving here means that sentence has been
    played out. That is how the agent learns how far a line got before it was talked over."""

    def __init__(self, owner: "VoiceTransport") -> None:
        super().__init__()
        self._owner = owner

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            if isinstance(frame, TTSTextFrame):
                self._owner._on_sentence_spoken(frame.text)
            elif isinstance(frame, BotStartedSpeakingFrame):
                self._owner._speaking.set()
                self._owner._idle.clear()
            elif isinstance(frame, BotStoppedSpeakingFrame):
                self._owner._speaking.clear()
                self._owner._idle.set()
            elif isinstance(frame, InterruptionFrame):
                self._owner._on_interrupted()
        await self.push_frame(frame, direction)


def _audio_from(speaker: str):
    heard_audio = False

    async def keep(frame: Frame) -> bool:
        nonlocal heard_audio
        if not isinstance(frame, InputAudioRawFrame):
            return True
        if frame.user_id != speaker:
            return False
        if not heard_audio:
            heard_audio = True
            # A speaker who never shows up here is not publishing a mic track (browser permission or
            # device problem), as opposed to audio arriving but not being transcribed.
            log.info("first audio frame from %s", speaker)
        return True

    return keep


class VoiceTransport(Transport):
    def __init__(
        self,
        room: BaseTransport,
        *,
        speakers: tuple[str, ...],
        joined_events: tuple[str, ...],
        left_events: tuple[str, ...],
    ) -> None:
        self._inbox: asyncio.Queue[str | None] = asyncio.Queue()
        self._joined = asyncio.Event()
        self._speaking = asyncio.Event()
        self._idle = asyncio.Event()
        self._idle.set()
        self._speakers = speakers
        self._sink: Callable[[str, str], None] | None = None
        self.on_left: Callable[[str], None] | None = None  # a participant (identity) left the room
        self.ended = False
        # The line last handed to send_text, the sentences of it played out so far, and -- once the
        # speaker talked over it -- how far it got (read once through take_interruption).
        self._line = ""
        self._spoken: list[str] = []
        self._interruption: Interruption | None = None

        self._room = room
        branches = [
            [
                FunctionFilter(_audio_from(speaker), filter_system_frames=True),
                get_stt_service(),
                # Sarvam's STT proposes a turn start when it hears speech; this turns that into an
                # interruption of the bot's speech. Only the main speaker (the patient) can cut the
                # agent off: the doctor talks over it on a merged call without muting it.
                *([UserTurnProcessor(user_turn_strategies=ExternalUserTurnStrategies())] if i == 0 else []),
                _Bridge(self, speaker),
            ]
            for i, speaker in enumerate(speakers)
        ]
        self._task = PipelineTask(
            Pipeline([
                room.input(), ParallelPipeline(*branches), get_tts_service(), room.output(),
                _SpeechTracker(self),
            ]),
        )
        self._runner_task: asyncio.Task | None = None

        async def on_joined(*_args) -> None:
            self._joined.set()

        async def on_left(*args) -> None:
            who = next((a for a in args if isinstance(a, str)), None)
            if who == speakers[0]:
                self._inbox.put_nowait(None)  # the main speaker hung up: unblocks receive_text
            if who is not None and self.on_left is not None:
                self.on_left(who)

        for name in joined_events:
            room.add_event_handler(name, on_joined)
        for name in left_events:
            room.add_event_handler(name, on_left)

    def set_sink(self, sink: Callable[[str, str], None]) -> None:
        """From now on transcripts go to `sink(speaker, text)` and the agent hears nothing."""
        self._sink = sink

    @property
    def joined(self) -> asyncio.Event:
        """Set once someone has entered the room."""
        return self._joined

    async def begin(self) -> None:
        """Start the pipeline without waiting for anyone to join."""
        if self._runner_task is None:
            self._runner_task = asyncio.create_task(PipelineRunner(handle_sigint=False).run(self._task))

    async def start(self) -> None:
        await self.begin()
        try:
            await asyncio.wait_for(self._joined.wait(), JOIN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            await self.abort()
            raise

    async def send_text(self, text: str) -> None:
        self._idle.clear()  # speech is pending until the output transport reports it finished
        self._line, self._spoken, self._interruption = text, [], None
        await self._task.queue_frame(TTSSpeakFrame(text))

    def take_interruption(self) -> Interruption | None:
        cut, self._interruption = self._interruption, None
        return cut

    def _on_sentence_spoken(self, sentence: str) -> None:
        self._spoken.append(sentence)

    def _on_interrupted(self) -> None:
        # Every start of a patient turn arrives here, including ones after the agent finished
        # speaking (idle): only a line still being spoken, or queued, has been cut off.
        if self._idle.is_set():
            return
        self._idle.set()  # whatever was queued is dropped, so no BotStoppedSpeaking may follow
        self._speaking.clear()
        line = " ".join(self._line.split())
        heard = " ".join(" ".join(self._spoken).split())
        # The frames carry the original text, so `heard` is normally a prefix of the line; if the TTS
        # reworded it, fall back to cutting at the same length.
        unheard = line[len(heard):].strip()
        if unheard:
            self._interruption = Interruption(heard=heard, unheard=unheard)

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
        if self._runner_task is not None and not self._runner_task.done():
            await self._task.cancel()
            await asyncio.gather(self._runner_task, return_exceptions=True)

    def _on_transcript(self, speaker: str, text: str) -> None:
        if self.ended:
            return
        log.info("transcript from %s (%d chars)", speaker, len(text))
        if self._sink is not None:
            self._sink(speaker, text)
        elif speaker == self._speakers[0]:
            self._inbox.put_nowait(text)
