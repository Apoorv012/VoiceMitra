from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.db import calls_col, doc_to_model
from backend.models import Call

router = APIRouter(prefix="/api/calls", tags=["calls"])


@router.get("/{call_id}", response_model=Call, response_model_by_alias=False)
async def get_call(call_id: str) -> Call:
    call = doc_to_model(Call, await calls_col().find_one({"_id": call_id}))
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    return call
