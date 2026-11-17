from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend import logins
from backend.access import require_staff
from backend.db import (
    caregivers_col,
    doc_to_model,
    doctors_col,
    model_to_doc,
    patients_col,
)
from backend.models import Caregiver, Patient
from backend.queries import get_patient_bundle
from backend.routers.devices import delete_caregiver_devices

# Staff only. (A patient's own endpoints under /api/patients/{id}/... -- calls, devices, login -- live in
# live.py, devices.py and auth.py with their own rules; prescriptions and medicines in medicines.py.)
router = APIRouter(prefix="/api/patients", tags=["patients"], dependencies=[Depends(require_staff)])


@router.get("", response_model=list[Patient], response_model_by_alias=False)
async def list_patients() -> list[Patient]:
    docs = await patients_col().find().to_list(length=500)
    return [doc_to_model(Patient, d) for d in docs]


class CaregiverInput(BaseModel):
    name: str
    relation: str
    phone_number: str


class CreatePatientRequest(BaseModel):
    name: str
    age: int
    description: str | None = None
    phone_number: str
    address: str | None = None
    allergies: list[str] = Field(default_factory=list)
    caregiver: CaregiverInput | None = None
    doctor_ids: list[str] = Field(default_factory=list)


async def _assign_doctors(patient_id: str, doctor_ids: list[str]) -> None:
    """Make exactly these doctors the patient's doctors (they are the ones rung on an escalation)."""
    await doctors_col().update_many({"patient_ids": patient_id, "_id": {"$nin": doctor_ids}},
                                    {"$pull": {"patient_ids": patient_id}})
    if doctor_ids:
        await doctors_col().update_many({"_id": {"$in": doctor_ids}}, {"$addToSet": {"patient_ids": patient_id}})


@router.post("", response_model=Patient, response_model_by_alias=False)
async def create_patient(body: CreatePatientRequest) -> Patient:
    patient = Patient(
        name=body.name,
        age=body.age,
        description=body.description,
        phone_number=body.phone_number,
        address=body.address,
        allergies=body.allergies,
    )
    if body.caregiver:
        caregiver = Caregiver(patient_id=patient.id, **body.caregiver.model_dump())
        await caregivers_col().insert_one(model_to_doc(caregiver))
        patient.caregiver_id = caregiver.id
    await patients_col().insert_one(model_to_doc(patient))
    await _assign_doctors(patient.id, body.doctor_ids)
    return patient


class PatientProfile(BaseModel):
    """What the edit form shows: the patient's own details, the family contact and who the doctors are."""
    id: str
    name: str
    age: int
    phone_number: str
    address: str | None
    description: str | None
    allergies: list[str]
    caregiver: CaregiverInput | None
    caregiver_id: str | None = None
    doctor_ids: list[str]


async def _profile(patient: Patient) -> PatientProfile:
    caregiver = None
    if patient.caregiver_id:
        caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": patient.caregiver_id}))
    doctor_ids = [d["_id"] async for d in doctors_col().find({"patient_ids": patient.id}, {"_id": 1})]
    return PatientProfile(
        id=patient.id, name=patient.name, age=patient.age, phone_number=patient.phone_number,
        address=patient.address, description=patient.description, allergies=patient.allergies,
        caregiver=CaregiverInput(name=caregiver.name, relation=caregiver.relation, phone_number=caregiver.phone_number)
        if caregiver else None,
        caregiver_id=caregiver.id if caregiver else None,
        doctor_ids=doctor_ids,
    )


@router.get("/{patient_id}/profile", response_model=PatientProfile)
async def get_profile(patient_id: str) -> PatientProfile:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return await _profile(patient)


class UpdatePatientRequest(BaseModel):
    """Only the fields sent are changed. `caregiver: null` removes the family contact."""
    name: str | None = None
    age: int | None = None
    phone_number: str | None = None
    address: str | None = None
    description: str | None = None
    allergies: list[str] | None = None
    caregiver: CaregiverInput | None = None
    doctor_ids: list[str] | None = None


@router.patch("/{patient_id}", response_model=PatientProfile)
async def update_patient(patient_id: str, body: UpdatePatientRequest) -> PatientProfile:
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": patient_id}))
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    sent = body.model_fields_set

    changes = {k: getattr(body, k) for k in ("name", "age", "phone_number", "address", "description", "allergies")
               if k in sent and (getattr(body, k) is not None or k in ("address", "description"))}
    if "caregiver" in sent:
        if body.caregiver is None:
            if patient.caregiver_id:
                await caregivers_col().delete_one({"_id": patient.caregiver_id})
                await logins.delete(patient.caregiver_id)
                await delete_caregiver_devices(patient.caregiver_id)
            changes["caregiver_id"] = None
        elif patient.caregiver_id:
            await caregivers_col().update_one({"_id": patient.caregiver_id}, {"$set": body.caregiver.model_dump()})
        else:
            caregiver = Caregiver(patient_id=patient_id, **body.caregiver.model_dump())
            await caregivers_col().insert_one(model_to_doc(caregiver))
            changes["caregiver_id"] = caregiver.id
    if changes:
        await patients_col().update_one({"_id": patient_id}, {"$set": changes})
    if body.doctor_ids is not None:
        await _assign_doctors(patient_id, body.doctor_ids)
    return await _profile(doc_to_model(Patient, await patients_col().find_one({"_id": patient_id})))


def _dump(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [v.model_dump(mode="json", by_alias=False) for v in value]
    return value.model_dump(mode="json", by_alias=False)


@router.get("/{patient_id}")
async def get_patient_detail(patient_id: str) -> dict:
    bundle = await get_patient_bundle(patient_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return {k: _dump(v) for k, v in bundle.items()}
