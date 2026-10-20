"""Shared plumbing for the server-rendered screens: the Jinja environment, wording for dates and
times, the Hindi/English switch, and "who is using this device".

There are no accounts. A person picks who they are once; that choice (and their language) lives in
cookies, so the installed app opens straight to their own home. That is a convenience, not security:
anyone can pick anyone, which is fine for the demo and is what a real sign-in would replace.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates

from backend.i18n import MESSAGES, MONTHS, WEEKDAYS
from backend.insights import ago as _ago, now_local, to_local

Role = Literal["patient", "doctor", "operator"]
ROLES: tuple[str, ...] = ("patient", "doctor", "operator")
LANGS = ("en", "hi")

WHO_COOKIE = "vm_who"
LANG_COOKIE = "vm_lang"
ONE_YEAR = 60 * 60 * 24 * 365


# --- who is using this device ---------------------------------------------------------------

def get_identity(request: Request) -> tuple[str, str | None] | None:
    """("patient", id) | ("doctor", id) | ("operator", None), or None if they haven't chosen."""
    raw = request.cookies.get(WHO_COOKIE, "")
    role, _, ident = raw.partition(":")
    if role == "operator":
        return ("operator", None)
    if role in ("patient", "doctor") and ident:
        return (role, ident)
    return None


def home_url(role: str, ident: str | None) -> str:
    return "/operator" if role == "operator" else f"/{role}s/{ident}"


def remember_identity(response: Response, role: str, ident: str | None) -> None:
    value = "operator" if role == "operator" else f"{role}:{ident}"
    response.set_cookie(WHO_COOKIE, value, max_age=ONE_YEAR, samesite="lax", path="/")


def forget_identity(response: Response) -> None:
    response.delete_cookie(WHO_COOKIE, path="/")


# --- language -------------------------------------------------------------------------------

def get_lang(request: Request) -> str:
    chosen = request.cookies.get(LANG_COOKIE)
    if chosen in LANGS:
        return chosen
    # No choice made yet: follow the browser, since most patients will be reading Hindi.
    header = request.headers.get("accept-language", "").lower()
    return "hi" if header.startswith("hi") else "en"


def translate(lang: str, key: str, **values) -> str:
    entry = MESSAGES.get(key)
    if entry is None:
        return key  # a missing string should be visible, not a crash
    text = entry.get(lang) or entry["en"]
    return text.format(**values) if values else text


# --- wording for dates and times -----------------------------------------------------------

def _local(value: datetime) -> datetime:
    return to_local(value)


def time_of(value: datetime) -> str:
    local = _local(value)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'}"


def day_of(value: datetime, lang: str = "en") -> str:
    """"Today", "Yesterday", or "Tue, 14 Oct" -- in the reader's language."""
    local = _local(value)
    delta = (now_local().date() - local.date()).days
    if delta == 0:
        return translate(lang, "today")
    if delta == 1:
        return translate(lang, "yesterday")
    return f"{WEEKDAYS[lang][local.weekday()]}, {local.day} {MONTHS[lang][local.month - 1]}"


def when(value: datetime, lang: str = "en") -> str:
    return f"{day_of(value, lang)}, {time_of(value)}"


def date_short(value: datetime, lang: str = "en") -> str:
    local = _local(value)
    return f"{local.day} {MONTHS[lang][local.month - 1]}"


def weekday_short(value, lang: str = "en") -> str:
    return WEEKDAYS[lang][value.weekday()]


def in_words(value: datetime, lang: str = "en") -> str:
    """How far away a time is: "in 2 h", "in 35 min", "now"."""
    seconds = int((to_local(value) - now_local()).total_seconds())
    if seconds <= 60:
        return translate(lang, "now")
    if seconds < 3600:
        return translate(lang, "in_min", n=seconds // 60)
    return translate(lang, "in_hours", n=round(seconds / 3600))


def initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p.lower() not in ("dr", "mr", "mrs", "ms")]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


def greeting(lang: str) -> str:
    hour = now_local().hour
    key = "good_morning" if hour < 12 else "good_afternoon" if hour < 17 else "good_evening"
    return translate(lang, key)


# --- the template environment -------------------------------------------------------------

def _context(request: Request) -> dict:
    lang = get_lang(request)
    return {
        "lang": lang,
        "t": lambda key, **values: translate(lang, key, **values),
        "identity": get_identity(request),
        "now": now_local(),
    }


templates = Jinja2Templates(
    directory=str(Path(__file__).parent / "templates"), context_processors=[_context],
)
templates.env.filters.update({
    "time_of": time_of, "day_of": day_of, "when": when, "date_short": date_short,
    "weekday_short": weekday_short, "in_words": in_words, "ago": _ago, "initials": initials,
})
templates.env.globals["greeting"] = greeting
