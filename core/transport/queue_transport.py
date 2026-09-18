"""In-process queue-backed transport: the agent's turns are appended to a message list, the other
party's replies arrive through `push_user_text` (e.g. from a WebSocket handler). Lets a web page
act as the "phone" -- the session loop runs as a background task, and whoever hosts it is told about
each message through `on_message` -- without the agent core knowing anything about HTTP."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from core.transport.base import Transport


@dataclass(frozen=True)
class Message:
    index: int
    role: str  # "agent" | "user"
    text: str


class QueueTransport(Transport):
    def __init__(self, on_message: Callable[[Message], None] | None = None) -> None:
        self._messages: list[Message] = []
        self._inbox: asyncio.Queue[str | None] = asyncio.Queue()
        self._on_message = on_message
        self.ended = False

    @property
    def messages(self) -> list[Message]:
        return list(self._messages)

    async def send_text(self, text: str) -> None:
        self._append("agent", text)

    async def receive_text(self) -> str | None:
        if self.ended:
            return None
        return await self._inbox.get()

    async def end(self) -> None:
        self.ended = True

    def push_user_text(self, text: str) -> None:
        if self.ended:
            return
        self._append("user", text)
        self._inbox.put_nowait(text)

    def hang_up(self) -> None:
        """Ask the session to finish: unblocks a pending `receive_text` with None."""
        self._inbox.put_nowait(None)

    def _append(self, role: str, text: str) -> None:
        message = Message(index=len(self._messages), role=role, text=text)
        self._messages.append(message)
        if self._on_message is not None:
            self._on_message(message)
