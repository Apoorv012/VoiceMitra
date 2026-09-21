from __future__ import annotations

from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import escalations, pages
from backend.db import ensure_indexes
from backend.live_calls import rearm_pending_reminders
from backend.routers import calls, doctors, live, patients
from backend.routers import escalations as escalation_routes

@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await escalations.abandon_stale()
    await rearm_pending_reminders()
    yield


app = FastAPI(title="VoiceMitra", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(calls.router)
app.include_router(live.router)
app.include_router(escalation_routes.router)
app.include_router(pages.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
