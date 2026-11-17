"""A patient's medicines: the two kinds (backend.models.PrescriptionSource).

- **Prescribed** -- staff add the doctor's prescription, typed in or read from a photo (the photo is only turned
  into a draft for staff to check; it is not stored). The patient sees these but can't change them.
- **Own** -- medicines the patient adds themself, from the website or the phone apps. Kept in one `own`
  prescription per patient, made on the first add. The patient (and staff) can edit and remove them.

Both kinds are scheduled, rung and asked about on calls the same way. Every change re-arms the dose timer.
"""

from __future__ import annotations

import base64
import binascii
import logging
import re
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from backend import dose_scheduler, insights
from backend.access import Principal, require_patient, require_staff
from backend.db import doc_to_model, dose_events_col, model_to_doc, patients_col, prescriptions_col
from backend.models import DoseFrequency, Dosage, Prescription, PrescriptionSource
from backend.prescription_photo import (
    IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    PhotoUnreadable,
    PrescriptionDraft,
    read_prescription_photo,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patients", tags=["medicines"])

MAX_OWN_MEDICINES = 30
_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")


class DosageInput(BaseModel):
    medicine_name: str = Field(min_length=1, max_length=80)
    dosage: str = Field(min_length=1, max_length=80)
    from_date: date
    to_date: date | None = None
    frequency: DoseFrequency
    times: list[str] = Field(default_factory=list, max_length=8)  # "HH:MM", 24-hour
    interval_days: int | None = Field(default=None, ge=1, le=90)  # required for every_x_days

    @field_validator("medicine_name", "dosage")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("can't be empty")
        return v

    @field_validator("times")
    @classmethod
    def _times(cls, v: list[str]) -> list[str]:
        out = set()
        for t in v:
            m = _TIME.match(t.strip())
            if not m or int(m[1]) > 23 or int(m[2]) > 59:
                raise ValueError(f"'{t}' isn't a time like 08:00 or 21:30")
            out.add(f"{int(m[1]):02d}:{m[2]}")
        return sorted(out)

    @model_validator(mode="after")
    def _check(self) -> "DosageInput":
        if self.frequency == DoseFrequency.every_x_days and not self.interval_days:
            raise ValueError("'every few days' needs interval_days (how many days apart)")
        if self.frequency != DoseFrequency.every_x_days:
            self.interval_days = None
        if self.to_date is not None and self.to_date < self.from_date:
            raise ValueError("the end date is before the start date")
        return self


class OwnMedicineInput(DosageInput):
    """A patient's own medicine needs at least one time: that is when the reminder call comes."""

    @field_validator("times")
    @classmethod
    def _need_a_time(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("add at least one time")
        return v


async def _patient_or_404(patient_id: str) -> dict:
    doc = await patients_col().find_one({"_id": patient_id}, {"prescription_ids": 1})
    if doc is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return doc


async def _new_prescription(patient_id: str, source: PrescriptionSource, medicines: list[DosageInput]) -> Prescription:
    rx = Prescription(patient_id=patient_id, source=source)
    rx.medicines = [Dosage(prescription_id=rx.id, **m.model_dump()) for m in medicines]
    await prescriptions_col().insert_one(model_to_doc(rx))
    await patients_col().update_one({"_id": patient_id}, {"$push": {"prescription_ids": rx.id}})
    return rx


# --- prescribed (staff) ---------------------------------------------------------------------

class AddPrescriptionRequest(BaseModel):
    medicines: list[DosageInput] = Field(min_length=1, max_length=20)


@router.post("/{patient_id}/prescriptions", response_model=Prescription, response_model_by_alias=False,
             dependencies=[Depends(require_staff)])
async def add_prescription(patient_id: str, body: AddPrescriptionRequest) -> Prescription:
    """Staff add the doctor's prescription (one or more medicines). The patient can't change these."""
    await _patient_or_404(patient_id)
    rx = await _new_prescription(patient_id, PrescriptionSource.prescribed, body.medicines)
    await dose_scheduler.arm(patient_id)  # new dose times may come sooner (no-op unless dose ringing is on)
    return rx


class PrescriptionPhoto(BaseModel):
    image_base64: str = Field(max_length=MAX_IMAGE_BYTES * 4 // 3 + 4)
    mime_type: str


@router.post("/{patient_id}/prescriptions/read-photo", response_model=PrescriptionDraft,
             dependencies=[Depends(require_staff)])
async def read_photo(patient_id: str, body: PrescriptionPhoto) -> PrescriptionDraft:
    """Read a photo of a prescription into draft medicines. Saves nothing: staff check the draft, then add it."""
    await _patient_or_404(patient_id)
    if body.mime_type not in IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="send a JPEG, PNG or WebP photo")
    try:
        raw = base64.b64decode(body.image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail="the photo couldn't be decoded") from None
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="the photo is too large")
    try:
        return await read_prescription_photo(body.image_base64, body.mime_type)
    except PhotoUnreadable:
        raise HTTPException(status_code=502, detail="couldn't read the prescription; try a clearer photo") from None
    except KeyError:  # no GEMINI_API_KEY on this server
        raise HTTPException(status_code=503, detail="reading photos isn't set up on this server") from None
    except Exception:
        log.exception("reading a prescription photo failed")
        raise HTTPException(status_code=502, detail="couldn't read the prescription right now; try again") from None


# --- the patient's own medicines, and editing either kind -------------------------------------

@router.post("/{patient_id}/own-medicines", response_model=Dosage, status_code=201)
async def add_own_medicine(patient_id: str, body: OwnMedicineInput,
                           _: Principal = Depends(require_patient)) -> Dosage:
    """The patient adds a medicine they take on their own (staff may add one for them too)."""
    patient = await _patient_or_404(patient_id)
    own = await prescriptions_col().find_one(
        {"_id": {"$in": patient.get("prescription_ids", [])}, "source": PrescriptionSource.own.value})
    if own is None:
        rx = await _new_prescription(patient_id, PrescriptionSource.own, [body])
        dosage = rx.medicines[0]
    else:
        if len(own.get("medicines", [])) >= MAX_OWN_MEDICINES:
            raise HTTPException(status_code=409, detail=f"at most {MAX_OWN_MEDICINES} of your own medicines")
        dosage = Dosage(prescription_id=own["_id"], **body.model_dump())
        await prescriptions_col().update_one({"_id": own["_id"]},
                                             {"$push": {"medicines": dosage.model_dump(mode="json")}})
    await dose_scheduler.arm(patient_id)
    return dosage


async def _find_dosage(patient_id: str, dosage_id: str, who: Principal) -> tuple[Prescription, Dosage]:
    patient = await _patient_or_404(patient_id)
    doc = await prescriptions_col().find_one(
        {"_id": {"$in": patient.get("prescription_ids", [])}, "medicines.id": dosage_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="medicine not found")
    rx = doc_to_model(Prescription, doc)
    if rx.source != PrescriptionSource.own and not who.is_staff:
        raise HTTPException(status_code=403, detail="only the clinic can change a prescribed medicine")
    return rx, next(m for m in rx.medicines if m.id == dosage_id)


async def _save(rx: Prescription) -> None:
    await prescriptions_col().update_one({"_id": rx.id},
                                         {"$set": {"medicines": [m.model_dump(mode="json") for m in rx.medicines]}})


@router.put("/{patient_id}/medicines/{dosage_id}", response_model=Dosage)
async def update_medicine(patient_id: str, dosage_id: str, body: DosageInput,
                          who: Principal = Depends(require_patient)) -> Dosage:
    """Change a medicine. The patient: only their own ones. Staff: either kind."""
    rx, old = await _find_dosage(patient_id, dosage_id, who)
    if rx.source == PrescriptionSource.own:
        body = OwnMedicineInput.model_validate(body.model_dump())
    new = Dosage(id=old.id, prescription_id=rx.id, **body.model_dump())
    rx.medicines = [new if m.id == dosage_id else m for m in rx.medicines]
    await _save(rx)
    await dose_scheduler.arm(patient_id)
    return new


class RemoveResult(BaseModel):
    # "stopped": it has doses on record, so it ends yesterday (today, if it only started today) and stays in the
    # past list with its history; "deleted": nothing was recorded for it, so it is gone.
    outcome: str


@router.delete("/{patient_id}/medicines/{dosage_id}", response_model=RemoveResult)
async def remove_medicine(patient_id: str, dosage_id: str, who: Principal = Depends(require_patient)) -> RemoveResult:
    """Remove a medicine (the patient: only their own). One with doses on record is stopped instead, so its
    history stays; an already finished one is deleted with its records."""
    rx, m = await _find_dosage(patient_id, dosage_id, who)
    today = insights.now_local().date()
    has_history = await dose_events_col().find_one({"patient_id": patient_id, "dosage_id": dosage_id}) is not None
    running = m.to_date is None or m.to_date >= today
    if has_history and running:
        m.to_date = max(m.from_date, today - timedelta(days=1))
        outcome = "stopped"
    else:
        rx.medicines = [x for x in rx.medicines if x.id != dosage_id]
        await dose_events_col().delete_many({"patient_id": patient_id, "dosage_id": dosage_id})
        outcome = "deleted"
    await _save(rx)
    await dose_scheduler.arm(patient_id)
    return RemoveResult(outcome=outcome)
