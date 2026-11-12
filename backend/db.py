"""Motor (async MongoDB) client + collection accessors mirroring backend/models.py."""

from __future__ import annotations

import os
from functools import lru_cache

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


@lru_cache
def get_client() -> AsyncIOMotorClient:
    uri = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    return AsyncIOMotorClient(uri)


def get_db() -> AsyncIOMotorDatabase:
    db_name = os.environ.get("MONGODB_DB_NAME", "voicemitra")
    return get_client()[db_name]


def patients_col():
    return get_db()["patients"]


def caregivers_col():
    return get_db()["caregivers"]


def prescriptions_col():
    return get_db()["prescriptions"]


def dose_events_col():
    return get_db()["dose_events"]


def doctors_col():
    return get_db()["doctors"]


def calls_col():
    return get_db()["calls"]


def daily_logs_col():
    return get_db()["daily_logs"]


def reminders_col():
    return get_db()["reminders"]


def escalations_col():
    return get_db()["escalations"]


def caregiver_notifications_col():
    return get_db()["caregiver_notifications"]


def devices_col():
    return get_db()["devices"]


def pairing_codes_col():
    return get_db()["pairing_codes"]


def contact_messages_col():
    return get_db()["contact_messages"]


def logins_col():
    return get_db()["logins"]


def web_sessions_col():
    return get_db()["web_sessions"]


async def ensure_indexes() -> None:
    # `_id` (== the domain id) is already indexed+unique by Mongo itself; only
    # foreign-key lookup fields need explicit indexes.
    await caregivers_col().create_index("patient_id")
    await prescriptions_col().create_index("patient_id")
    await dose_events_col().create_index("patient_id")
    await calls_col().create_index("patient_id")
    await calls_col().create_index("doctor_id")
    await daily_logs_col().create_index("patient_id")
    await reminders_col().create_index([("patient_id", 1), ("status", 1)])
    await escalations_col().create_index("doctor_ids")
    await escalations_col().create_index("call_id")
    await caregiver_notifications_col().create_index("patient_id")
    await devices_col().create_index("patient_id")
    await devices_col().create_index("push_token")
    await pairing_codes_col().create_index("code")
    await contact_messages_col().create_index("created_at")
    await logins_col().create_index("username_key", unique=True)
    await web_sessions_col().create_index("subject_id")
    # Mongo deletes a session once `expires_at` (a real BSON date, unlike most dates here) has passed.
    await web_sessions_col().create_index("expires_at", expireAfterSeconds=0)
    await _move_patient_logins()


async def _move_patient_logins() -> None:
    """Phone-app logins used to live in `patient_logins` (patients only). Copy them into `logins` once."""
    old = get_db()["patient_logins"]
    async for doc in old.find():
        clash = await logins_col().find_one({"username_key": doc["username_key"], "_id": {"$ne": doc["_id"]}})
        if clash is not None:
            print(f"[logins] not moving patient login {doc['username']!r}: the username is taken; set it again")
            continue  # left in `patient_logins`, nothing lost
        if await logins_col().find_one({"_id": doc["_id"]}) is None:
            await logins_col().insert_one({**doc, "role": "patient"})
        await old.delete_one({"_id": doc["_id"]})


def doc_to_model(model_cls, doc: dict | None):
    """Build a model (a MongoDocument subclass) from a raw Mongo document.

    `_id` maps straight to the model's aliased `id` field -- no separate id to
    strip or reconcile.
    """
    if doc is None:
        return None
    return model_cls(**doc)


def model_to_doc(model) -> dict:
    """Dump a MongoDocument for insertion, writing its id out as `_id`."""
    return model.model_dump(mode="json", by_alias=True)
