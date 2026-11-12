"""The contact form on the public homepage, and the operator's inbox for it.

Anyone can send a message (no sign-in), so the endpoint is guarded three ways: field lengths are capped,
a hidden "website" field catches simple bots (a person never fills it), and the whole form pauses after
MAX_MESSAGES in WINDOW_SECONDS. Nothing is emailed: operators read messages at /operator/messages (staff only).
"""

from __future__ import annotations

import re
import time
from collections import deque
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.access import require_staff
from backend.db import contact_messages_col, doc_to_model, model_to_doc
from backend.models import ContactMessage, ContactTopic

router = APIRouter(tags=["contact"])

MAX_MESSAGES = 30
WINDOW_SECONDS = 10 * 60
_recent: deque[float] = deque()

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    organisation: str | None = Field(default=None, max_length=150)
    topic: ContactTopic = ContactTopic.demo
    message: str = Field(min_length=1, max_length=4000)
    website: str | None = Field(default=None, max_length=200)  # honeypot: hidden on the form

    @field_validator("name", "email", "message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        if not EMAIL.match(value):
            raise ValueError("not an email address")
        return value

    @field_validator("phone", "organisation")
    @classmethod
    def _optional(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class ContactReceipt(BaseModel):
    id: str


class ContactMessageView(BaseModel):
    """A message as the operator's inbox shows it (plain `id`, never Mongo's `_id`)."""

    id: str
    name: str
    email: str
    phone: str | None
    organisation: str | None
    topic: ContactTopic
    message: str
    handled: bool
    created_at: datetime


class HandledRequest(BaseModel):
    handled: bool


def _too_many() -> bool:
    cutoff = time.monotonic() - WINDOW_SECONDS
    while _recent and _recent[0] < cutoff:
        _recent.popleft()
    return len(_recent) >= MAX_MESSAGES


@router.post("/api/contact", response_model=ContactReceipt, status_code=201,
             responses={429: {"description": "too many messages lately, paused"}})
async def send_message(body: ContactRequest) -> ContactReceipt:
    if _too_many():
        raise HTTPException(status_code=429, detail="too many messages right now, try again in a few minutes")
    _recent.append(time.monotonic())
    message = ContactMessage(**body.model_dump(exclude={"website"}))
    if not body.website:  # a bot filled the hidden field: answer as usual, keep nothing
        await contact_messages_col().insert_one(model_to_doc(message))
    return ContactReceipt(id=message.id)


@router.get("/api/contact", response_model=list[ContactMessageView], dependencies=[Depends(require_staff)])
async def list_messages() -> list[ContactMessageView]:
    """Newest first (the last 200)."""
    cursor = contact_messages_col().find().sort("created_at", -1).limit(200)
    return [ContactMessageView(**doc_to_model(ContactMessage, doc).model_dump()) async for doc in cursor]


@router.put("/api/contact/{message_id}/handled", status_code=204, responses={404: {"description": "no such message"}},
            dependencies=[Depends(require_staff)])
async def set_handled(message_id: str, body: HandledRequest) -> None:
    result = await contact_messages_col().update_one({"_id": message_id}, {"$set": {"handled": body.handled}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="message not found")
