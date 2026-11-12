"""Usernames + passwords for everyone who signs in: staff, patients and caregivers.

One `logins` collection, so a username is unique across all of them. Patients use the same login on
the website and in the phone apps; caregivers and staff only on the website. Staff logins are made with
`python -m backend.create_staff`; patient and caregiver logins are set from the staff screens.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from backend.auth import DUMMY_HASH, hash_password, verify_password
from backend.db import doc_to_model, logins_col, model_to_doc, web_sessions_col
from backend.models import Login, LoginRole

MIN_PASSWORD = 6
MIN_USERNAME, MAX_USERNAME = 3, 40

# Failed logins allowed per window before logins are paused. Counted across all callers (behind the
# tunnel and Vercel every request can carry the same address), and separately per username, so one
# person's account is paused well before everyone's is.
MAX_BAD_LOGINS = 20
MAX_BAD_PER_USERNAME = 5
BAD_LOGIN_WINDOW_SECONDS = 600

_bad_logins: deque[float] = deque()
_bad_by_username: defaultdict[str, deque[float]] = defaultdict(deque)


def username_key(username: str) -> str:
    return username.strip().casefold()


async def get(subject_id: str) -> Login | None:
    return doc_to_model(Login, await logins_col().find_one({"_id": subject_id}))


async def find(username: str) -> Login | None:
    return doc_to_model(Login, await logins_col().find_one({"username_key": username_key(username)}))


async def set_login(role: LoginRole, subject_id: str, username: str, password: str,
                    keep_session_hash: str | None = None) -> Login:
    """Create or change a login. Signs the person out everywhere on the website except `keep_session_hash`
    (the session making the change). Phones already signed in stay signed in (unpair them separately)."""
    username = username.strip()
    if not MIN_USERNAME <= len(username) <= MAX_USERNAME:
        raise HTTPException(status_code=400, detail=f"username must be {MIN_USERNAME}-{MAX_USERNAME} characters")
    if len(password) < MIN_PASSWORD:
        raise HTTPException(status_code=400, detail=f"password must be at least {MIN_PASSWORD} characters")
    key = username_key(username)
    taken = await logins_col().find_one({"username_key": key, "_id": {"$ne": subject_id}}, {"_id": 1})
    if taken is not None:
        raise HTTPException(status_code=409, detail="username already taken")
    existing = await get(subject_id)
    if existing is not None and existing.role != role:
        raise HTTPException(status_code=409, detail="this id already has a login of another kind")
    login = Login(id=subject_id, role=role, username=username, username_key=key,
                  password_hash=await asyncio.to_thread(hash_password, password))
    try:
        await logins_col().replace_one({"_id": subject_id}, model_to_doc(login), upsert=True)
    except DuplicateKeyError:  # someone took it between the check and the write
        raise HTTPException(status_code=409, detail="username already taken") from None
    await revoke_sessions(subject_id, keep=keep_session_hash)
    return login


async def delete(subject_id: str) -> None:
    """Remove the login and sign the person out of the website. Phones stay paired (unpair separately)."""
    await logins_col().delete_one({"_id": subject_id})
    await revoke_sessions(subject_id)


async def revoke_sessions(subject_id: str, keep: str | None = None) -> None:
    query: dict = {"subject_id": subject_id}
    if keep:
        query["_id"] = {"$ne": keep}
    await web_sessions_col().delete_many(query)


def _prune(q: deque[float], cutoff: float) -> None:
    while q and q[0] < cutoff:
        q.popleft()


async def check(username: str, password: str) -> Login | None:
    """The login these credentials belong to, or None. Raises 429 while logins are paused.

    A wrong username takes as long as a wrong password, and both give the same answer."""
    key = username_key(username)
    cutoff = time.monotonic() - BAD_LOGIN_WINDOW_SECONDS
    _prune(_bad_logins, cutoff)
    _prune(_bad_by_username[key], cutoff)
    if len(_bad_logins) >= MAX_BAD_LOGINS or len(_bad_by_username[key]) >= MAX_BAD_PER_USERNAME:
        raise HTTPException(status_code=429, detail="too many failed logins, try again in a few minutes")
    login = await find(username)
    ok = await asyncio.to_thread(verify_password, password, login.password_hash if login else DUMMY_HASH)
    if ok and login is not None:
        return login
    now = time.monotonic()
    _bad_logins.append(now)
    _bad_by_username[key].append(now)
    if len(_bad_by_username) > 10_000:  # don't let made-up usernames grow this forever
        _bad_by_username.clear()
    return None
