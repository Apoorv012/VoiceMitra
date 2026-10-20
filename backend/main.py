from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from backend import escalations
from backend.db import ensure_indexes
from backend.live_calls import rearm_pending_reminders
from backend.routers import app_api, calls, doctors, live, patients
from backend.routers import escalations as escalation_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await escalations.abandon_stale()
    await rearm_pending_reminders()
    yield


# The backend is an API only: JSON and WebSockets. The screens live in the web app (web/).
app = FastAPI(title="VoiceMitra", lifespan=lifespan)

app.include_router(app_api.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(calls.router)
app.include_router(live.router)
app.include_router(escalation_routes.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
