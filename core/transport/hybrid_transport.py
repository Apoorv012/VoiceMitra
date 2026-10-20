"""Text and voice on one conversation: the doctor's briefing.

The agent's lines always go to the text channel (so the page shows them as captions) and are also
spoken once the other party has joined the voice room, and a reply can arrive either typed or
spoken (spoken replies are echoed into the text channel as captions). Nobody is forced into voice: a
doctor who never joins the room, or who loses their microphone, carries on by typing.

The text channel outlives this transport. After the briefing it keeps carrying the merged call's
captions, so `end()` here only winds down the voice side.
"""

from __future__ import annotations

import asyncio

from core.transport.base import Interruption, Transport
from core.transport.queue_transport import QueueTransport
from core.transport.voice_pipeline import VoiceTransport


class HybridTransport(Transport):
    def __init__(self, text: QueueTransport, voice: VoiceTransport) -> None:
        self._text = text
        self._voice = voice
        self._pending: list[str] = []      # lines sent before anyone joined the voice room
        self._voice_live = False           # joined, and the backlog has been spoken
        self._voice_gone = False           # the voice speaker left the room; typing still works
        self._typed: asyncio.Task | None = None
        self._spoken: asyncio.Task | None = None
        self._flusher: asyncio.Task | None = None

    async def start(self) -> None:
        await self._voice.begin()  # don't wait for the join: the text channel works without it
        self._flusher = asyncio.create_task(self._speak_backlog_once_joined())

    async def _speak_backlog_once_joined(self) -> None:
        await self._voice.joined.wait()
        # Lines may be added while earlier ones are queued, so drain until empty; the flag is set
        # with no await between the last emptiness check and the assignment.
        while self._pending:
            await self._voice.send_text(self._pending.pop(0))
        self._voice_live = True

    async def send_text(self, text: str) -> None:
        await self._text.send_text(text)
        if self._voice_live:
            await self._voice.send_text(text)
        else:
            self._pending.append(text)

    async def receive_text(self) -> str | None:
        while True:
            if self._typed is None:
                self._typed = asyncio.ensure_future(self._text.receive_text())
            if self._spoken is None and not self._voice_gone:
                self._spoken = asyncio.ensure_future(self._voice.receive_text())
            waiting = {t for t in (self._typed, self._spoken) if t is not None}
            done, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
            if self._typed in done:
                text, self._typed = self._typed.result(), None
                return text  # None: the text side hung up
            text, self._spoken = self._spoken.result(), None
            if text is None:
                self._voice_gone = True
                continue
            self._text.add_message("user", text)
            return text

    def take_interruption(self) -> Interruption | None:
        return self._voice.take_interruption()

    async def end(self) -> None:
        """Let a line being spoken finish, then close the voice side (not the text channel)."""
        await self._voice.end()
        self._stop_tasks()

    async def abort(self) -> None:
        """Drop the voice side immediately; safe to call after `end()`."""
        self._stop_tasks()
        await self._voice.abort()

    def _stop_tasks(self) -> None:
        for task in (self._typed, self._spoken, self._flusher):
            if task is not None and not task.done():
                task.cancel()
