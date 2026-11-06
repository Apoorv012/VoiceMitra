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


@pytest.fixture
async def client(mongo):
    import httpx

    from backend.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c
