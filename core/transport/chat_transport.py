"""Terminal REPL transport: agent text printed to stdout, the other party's reply typed at a
prompt. Used to build and debug agent logic (Chunk 2) before real voice is wired in (Chunk 3)."""

from __future__ import annotations

import asyncio

from core.transport.base import Transport

END_COMMANDS = {"/end", "/quit", "/exit"}


class ChatTransport(Transport):
    def __init__(self, speaker_label: str = "Patient") -> None:
        self._speaker_label = speaker_label
        self._ended = False

    async def start(self) -> None:
        print(f"--- chat session started (type {'/end'!r} to hang up) ---")

    async def send_text(self, text: str) -> None:
        print(f"\nAgent: {text}\n")

    async def receive_text(self) -> str | None:
        if self._ended:
            return None
        line = await asyncio.to_thread(input, f"{self._speaker_label}: ")
        if line.strip().lower() in END_COMMANDS:
            self._ended = True
            return None
        return line

    async def end(self) -> None:
        self._ended = True
        print("--- chat session ended ---")
