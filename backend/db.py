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


async def ensure_indexes() -> None:
    # `_id` (== the domain id) is already indexed+unique by Mongo itself; only
    # foreign-key lookup fields need explicit indexes.
    await caregivers_col().create_index("patient_id")
    await prescriptions_col().create_index("patient_id")
    await dose_events_col().create_index("patient_id")
    await calls_col().create_index("patient_id")
    await calls_col().create_index("doctor_id")
    await daily_logs_col().create_index("patient_id")


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
