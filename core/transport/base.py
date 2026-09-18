"""Transport interface: what the agent core needs from any call medium.

Deliberately text-in/text-out: a voice transport (Chunk 3, Daily+Sarvam STT/TTS) converts
audio<->text at its own edges before handing turns to the agent core through this same interface;
a text transport (this chunk) passes strings straight through. Either way, core/agent/ and
domains/med_adherence/ never see the underlying medium -- that's the whole point.

A future phone transport (Twilio) is a second Transport implementation, not a change to anything
that imports Transport.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Transport(ABC):
    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Deliver the agent's turn (spoken via TTS for voice, printed for chat)."""

    @abstractmethod
    async def receive_text(self) -> str | None:
        """Return the other party's next utterance, or None once the call/session has ended."""

    async def start(self) -> None:
        """Optional hook: join a room, print a banner, etc. No-op by default."""

    async def end(self) -> None:
        """Optional hook: hang up, close a room, etc. No-op by default."""
