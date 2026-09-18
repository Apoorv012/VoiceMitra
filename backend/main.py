from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from backend.db import doc_to_model, ensure_indexes, patients_col
from backend.models import Patient

app = FastAPI(title="VoiceMitra")


@app.on_event("startup")
async def on_startup() -> None:
    await ensure_indexes()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/patients", response_model=list[Patient], response_model_by_alias=False)
async def list_patients() -> list[Patient]:
    docs = await patients_col().find().to_list(length=200)
    return [doc_to_model(Patient, d) for d in docs]
