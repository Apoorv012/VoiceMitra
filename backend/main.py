from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend import pages
from backend.db import ensure_indexes
from backend.live_calls import rearm_pending_reminders
from backend.routers import calls, doctors, live, patients

app = FastAPI(title="VoiceMitra")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(calls.router)
app.include_router(live.router)
app.include_router(pages.router)


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()
    await rearm_pending_reminders()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
