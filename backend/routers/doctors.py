from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db import doc_to_model, doctors_col
from backend.models import Doctor
from backend.queries import get_doctor_bundle

router = APIRouter(prefix="/api/doctors", tags=["doctors"])


@router.get("", response_model=list[Doctor], response_model_by_alias=False)
async def list_doctors() -> list[Doctor]:
    docs = await doctors_col().find().to_list(length=200)
    return [doc_to_model(Doctor, d) for d in docs]


def _dump(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [v.model_dump(mode="json", by_alias=False) for v in value]
    return value.model_dump(mode="json", by_alias=False)


@router.get("/{doctor_id}")
async def get_doctor_detail(doctor_id: str) -> dict:
    bundle = await get_doctor_bundle(doctor_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="doctor not found")
    return {k: _dump(v) for k, v in bundle.items()}
