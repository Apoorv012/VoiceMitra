"""/health/ready is what the deploy waits on (deploy/remote-deploy.sh): ok only when MongoDB answers."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio


async def test_ready_when_db_answers(client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


async def test_not_ready_when_db_is_down(client, monkeypatch):
    from backend import main

    class DownDb:
        async def command(self, *_):
            raise ConnectionError("no db")

    monkeypatch.setattr(main, "get_db", lambda: DownDb())
    r = await client.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "db_unreachable"
