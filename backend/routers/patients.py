from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.db import (
    caregivers_col,
    doc_to_model,
    model_to_doc,
    patients_col,
    prescriptions_col,
)
from backend.models import Caregiver, DoseFrequency, Dosage, Patient, Prescription
from backend.queries import get_patient_bundle

router = APIRouter(prefix="/api/patients", tags=["patients"])


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
    return patient


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


class DosageInput(BaseModel):
    medicine_name: str
    dosage: str
    from_date: str
    to_date: str | None = None
    frequency: DoseFrequency
    times: list[str] = Field(default_factory=list)


class AddPrescriptionRequest(BaseModel):
    medicines: list[DosageInput]


@router.post("/{patient_id}/prescriptions", response_model=Prescription, response_model_by_alias=False)
async def add_prescription(patient_id: str, body: AddPrescriptionRequest) -> Prescription:
    patient_doc = await patients_col().find_one({"_id": patient_id})
    if patient_doc is None:
        raise HTTPException(status_code=404, detail="patient not found")

    prescription = Prescription(patient_id=patient_id)
    prescription.medicines = [
        Dosage(prescription_id=prescription.id, **m.model_dump()) for m in body.medicines
    ]
    await prescriptions_col().insert_one(model_to_doc(prescription))
    await patients_col().update_one(
        {"_id": patient_id}, {"$push": {"prescription_ids": prescription.id}}
    )
    return prescription
