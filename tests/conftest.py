"""Shared fixtures. Tests that need MongoDB use `mongo`: a throwaway database (name ends in `test`) on
the local server, dropped afterwards -- never the real `voicemitra` one."""

from __future__ import annotations

import os

import pytest

TEST_DB = "voicemitra_pytest_test"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def mongo(monkeypatch):
    from backend import db

    monkeypatch.setenv("MONGODB_DB_NAME", TEST_DB)
    # Always the local server (or TEST_MONGODB_URI), never the MONGODB_URI in .env, which may be the cloud database.
    monkeypatch.setenv("MONGODB_URI", os.environ.get("TEST_MONGODB_URI", "mongodb://localhost:27017"))
    db.get_client.cache_clear()  # a fresh client on this test's event loop
    try:
        await db.get_client().drop_database(TEST_DB)
        await db.ensure_indexes()
    except Exception as e:  # no local mongod
        db.get_client.cache_clear()
        if os.environ.get("CI"):  # CI starts a MongoDB for the tests: a skip there would hide a broken setup
            pytest.fail(f"MongoDB not reachable in CI: {e}")
        pytest.skip(f"MongoDB not reachable: {e}")
    yield db.get_db()
    await db.get_client().drop_database(TEST_DB)
    db.get_client.cache_clear()


async def session_cookie(role: str, subject_id: str) -> str:
    """A website session for this person (as if they had signed in); returns the cookie value."""
    from backend import access
    from backend.models import Login, LoginRole

    login = Login(id=subject_id, role=LoginRole(role), username=f"{role}-{subject_id}"[:40], username_key="-",
                  password_hash="-")
    token, _ = await access.create_session(login)
    return token


def _client(app, cookie: str | None = None):
    import httpx

    from backend.access import SESSION_COOKIE

    # https, so the session cookie (Secure) is sent back like a browser would.
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test")
    if cookie:
        c.cookies.set(SESSION_COOKIE, cookie)
    return c


@pytest.fixture
async def client(mongo):
    """Signed in as staff, who may call everything (most tests are about behaviour, not access)."""
    from backend.main import app

    async with _client(app, await session_cookie("staff", "staff-test")) as c:
        yield c


@pytest.fixture
async def anon_client(mongo):
    """Not signed in."""
    from backend.main import app

    async with _client(app) as c:
        yield c


@pytest.fixture
async def client_as(mongo):
    """`await client_as("patient", patient_id)` -> a client signed in as that person (closed after the test)."""
    from backend.main import app

    opened = []

    async def make(role: str, subject_id: str):
        c = _client(app, await session_cookie(role, subject_id))
        opened.append(c)
        return c

    yield make
    for c in opened:
        await c.aclose()
