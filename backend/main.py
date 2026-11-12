from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend import dose_scheduler, escalations
from backend.db import ensure_indexes, get_db
from backend.live_calls import rearm_pending_reminders
from backend.routers import app_api, calls, caregivers, contact, devices, doctors, live, patients
from backend.routers import escalations as escalation_routes
from backend.routers import auth as auth_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()
    await escalations.abandon_stale()
    await rearm_pending_reminders()
    await dose_scheduler.start()  # off unless DOSE_RINGING_ENABLED
    yield
    dose_scheduler.stop()


# The backend is an API only: JSON and WebSockets. The screens live in the web app (web/). Who may call
# what: backend/access.py. The interactive docs (/docs, /redoc, /openapi.json) are off unless
# API_DOCS_ENABLED=true (set it in a local .env); `python -m backend.dump_openapi` still writes the schema.
_docs = os.environ.get("API_DOCS_ENABLED", "false").lower() == "true"
app = FastAPI(title="VoiceMitra", lifespan=lifespan, docs_url="/docs" if _docs else None,
              redoc_url="/redoc" if _docs else None, openapi_url="/openapi.json" if _docs else None)

app.include_router(app_api.router)
app.include_router(patients.router)
app.include_router(doctors.router)
app.include_router(calls.router)
app.include_router(live.router)
app.include_router(caregivers.router)
app.include_router(escalation_routes.router)
app.include_router(devices.router)
app.include_router(auth_routes.router)
app.include_router(contact.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)  # for the server, not part of the web/app contract
async def ready() -> JSONResponse:
    """Like /health, but also checks MongoDB answers. The deploy waits on this, so a wrong MONGODB_URI
    (or an Atlas IP allowlist that misses the server) fails the deploy instead of looking healthy."""
    try:
        await asyncio.wait_for(get_db().command("ping"), timeout=5)
    except Exception as e:
        return JSONResponse({"status": "db_unreachable", "error": type(e).__name__}, status_code=503)
    return JSONResponse({"status": "ok", "version": os.environ.get("GIT_SHA", "dev")})
