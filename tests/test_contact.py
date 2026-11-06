"""The homepage contact form and the operator's inbox for it (backend/routers/contact.py)."""

from __future__ import annotations

import pytest

from backend.routers import contact

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _fresh_limiter(monkeypatch):
    monkeypatch.setattr(contact, "_recent", type(contact._recent)())


def _form(**over):
    body = {"name": "Dr. Rao", "email": "rao@clinic.in", "phone": "+91 98765 43210", "organisation": "Rao Clinic",
            "topic": "pilot", "message": "We'd like to try this with 20 patients."}
    body.update(over)
    return body


async def test_send_and_list(client, mongo):
    res = await client.post("/api/contact", json=_form(name="  Dr. Rao  ", organisation="  "))
    assert res.status_code == 201
    message_id = res.json()["id"]

    listed = (await client.get("/api/contact")).json()
    assert len(listed) == 1
    row = listed[0]
    assert row["id"] == message_id and "_id" not in row
    assert row["name"] == "Dr. Rao"          # trimmed
    assert row["organisation"] is None       # blank becomes empty
    assert row["topic"] == "pilot" and row["handled"] is False


async def test_newest_first(client, mongo):
    for name in ("First", "Second"):
        assert (await client.post("/api/contact", json=_form(name=name))).status_code == 201
    assert [m["name"] for m in (await client.get("/api/contact")).json()] == ["Second", "First"]


@pytest.mark.parametrize("over", [
    {"email": "not-an-email"},
    {"name": "   "},
    {"message": ""},
    {"message": "x" * 4001},
    {"topic": "spam"},
])
async def test_rejects_bad_input(client, mongo, over):
    assert (await client.post("/api/contact", json=_form(**over))).status_code == 422
    assert (await client.get("/api/contact")).json() == []


async def test_honeypot_is_dropped_quietly(client, mongo):
    res = await client.post("/api/contact", json=_form(website="http://spam.example"))
    assert res.status_code == 201
    assert (await client.get("/api/contact")).json() == []


async def test_mark_handled(client, mongo):
    message_id = (await client.post("/api/contact", json=_form())).json()["id"]
    url = f"/api/contact/{message_id}/handled"
    assert (await client.put(url, json={"handled": True})).status_code == 204
    assert (await client.get("/api/contact")).json()[0]["handled"] is True
    assert (await client.put(url, json={"handled": False})).status_code == 204
    assert (await client.get("/api/contact")).json()[0]["handled"] is False
    assert (await client.put("/api/contact/nope/handled", json={"handled": True})).status_code == 404


async def test_pauses_after_too_many(client, mongo, monkeypatch):
    monkeypatch.setattr(contact, "MAX_MESSAGES", 2)
    for _ in range(2):
        assert (await client.post("/api/contact", json=_form())).status_code == 201
    assert (await client.post("/api/contact", json=_form())).status_code == 429
