"""Server-rendered HTML dashboards: operator (hospital staff), doctor, and patient/family
self-view. Reuses the same db helpers as the JSON routers rather than calling them over HTTP."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.db import (
    calls_col,
    caregivers_col,
    doc_to_model,
    doctors_col,
    model_to_doc,
    patients_col,
    prescriptions_col,
)
from backend.models import Call, Caregiver, Doctor, DoseFrequency, Dosage, Patient, Prescription
from backend.queries import get_doctor_bundle, get_patient_bundle, list_patients_with_last_status

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _dump(value):
    if value is None:
        return None
    if isinstance(value, list):
        return [v.model_dump(mode="json", by_alias=False) for v in value]
    return value.model_dump(mode="json", by_alias=False)


@router.get("/")
async def home(request: Request):
    patients = [doc_to_model(Patient, d) async for d in patients_col().find()]
    doctors = [doc_to_model(Doctor, d) async for d in doctors_col().find()]
    return templates.TemplateResponse(request, "home.html", {"patients": patients, "doctors": doctors})


@router.get("/operator")
async def operator_dashboard(request: Request):
    rows = await list_patients_with_last_status()
    return templates.TemplateResponse(request, "operator.html", {"rows": rows})


@router.post("/operator/patients")
async def operator_create_patient(
    name: str = Form(...),
    age: int = Form(...),
    phone_number: str = Form(...),
    address: str = Form(""),
    allergies: str = Form(""),
    description: str = Form(""),
    caregiver_name: str = Form(""),
    caregiver_relation: str = Form(""),
    caregiver_phone: str = Form(""),
):
    patient = Patient(
        name=name,
        age=age,
        phone_number=phone_number,
        address=address or None,
        description=description or None,
        allergies=[a.strip() for a in allergies.split(",") if a.strip()],
    )
    if caregiver_name:
        caregiver = Caregiver(patient_id=patient.id, name=caregiver_name,
                               relation=caregiver_relation or "family", phone_number=caregiver_phone)
        await caregivers_col().insert_one(model_to_doc(caregiver))
        patient.caregiver_id = caregiver.id
    await patients_col().insert_one(model_to_doc(patient))
    return RedirectResponse(url="/operator", status_code=303)


async def _render_patient_detail(request: Request, patient_id: str, *, editable: bool,
                                  back_link: str | None, add_prescription_action: str):
    bundle = await get_patient_bundle(patient_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="patient not found")
    context = {k: _dump(v) for k, v in bundle.items()}
    context.update({
        "editable": editable,
        "back_link": back_link,
        "add_prescription_action": add_prescription_action,
    })
    return templates.TemplateResponse(request, "patient_detail.html", context)


@router.get("/operator/patients/{patient_id}")
async def operator_patient_detail(request: Request, patient_id: str):
    return await _render_patient_detail(
        request, patient_id, editable=True, back_link="/operator",
        add_prescription_action=f"/operator/patients/{patient_id}/prescriptions",
    )


async def _add_prescription(
    patient_id: str, *, medicine_name: str, dosage: str, frequency: DoseFrequency,
    times: str, from_date: str, to_date: str,
) -> None:
    patient_doc = await patients_col().find_one({"_id": patient_id})
    if patient_doc is None:
        raise HTTPException(status_code=404, detail="patient not found")

    prescription = Prescription(patient_id=patient_id)
    prescription.medicines = [Dosage(
        prescription_id=prescription.id,
        medicine_name=medicine_name,
        dosage=dosage,
        from_date=from_date,
        to_date=to_date or None,
        frequency=frequency,
        times=[t.strip() for t in times.split(",") if t.strip()],
    )]
    await prescriptions_col().insert_one(model_to_doc(prescription))
    await patients_col().update_one({"_id": patient_id}, {"$push": {"prescription_ids": prescription.id}})


@router.post("/operator/patients/{patient_id}/prescriptions")
async def operator_add_prescription(
    patient_id: str,
    medicine_name: str = Form(...),
    dosage: str = Form(...),
    frequency: DoseFrequency = Form(...),
    times: str = Form(""),
    from_date: str = Form(...),
    to_date: str = Form(""),
):
    await _add_prescription(patient_id, medicine_name=medicine_name, dosage=dosage,
                             frequency=frequency, times=times, from_date=from_date, to_date=to_date)
    return RedirectResponse(url=f"/operator/patients/{patient_id}", status_code=303)


@router.get("/patients/{patient_id}")
async def patient_self_view(request: Request, patient_id: str):
    return await _render_patient_detail(
        request, patient_id, editable=False, back_link=None, add_prescription_action="",
    )


@router.get("/doctors/{doctor_id}")
async def doctor_dashboard(request: Request, doctor_id: str):
    bundle = await get_doctor_bundle(doctor_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="doctor not found")
    patient_names = {p.id: p.name for p in bundle["patients"]}
    context = {
        "doctor": bundle["doctor"],
        "patients": bundle["patients"],
        "escalations": _dump(bundle["escalations"]),
        "patient_names": patient_names,
    }
    return templates.TemplateResponse(request, "doctor_dashboard.html", context)


@router.get("/doctors/{doctor_id}/patients/{patient_id}")
async def doctor_patient_detail(request: Request, doctor_id: str, patient_id: str):
    return await _render_patient_detail(
        request, patient_id, editable=True, back_link=f"/doctors/{doctor_id}",
        add_prescription_action=f"/doctors/{doctor_id}/patients/{patient_id}/prescriptions",
    )


@router.post("/doctors/{doctor_id}/patients/{patient_id}/prescriptions")
async def doctor_add_prescription(
    doctor_id: str,
    patient_id: str,
    medicine_name: str = Form(...),
    dosage: str = Form(...),
    frequency: DoseFrequency = Form(...),
    times: str = Form(""),
    from_date: str = Form(...),
    to_date: str = Form(""),
):
    await _add_prescription(patient_id, medicine_name=medicine_name, dosage=dosage,
                             frequency=frequency, times=times, from_date=from_date, to_date=to_date)
    return RedirectResponse(url=f"/doctors/{doctor_id}/patients/{patient_id}", status_code=303)


@router.get("/calls/{call_id}")
async def call_detail(request: Request, call_id: str):
    call = doc_to_model(Call, await calls_col().find_one({"_id": call_id}))
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    return templates.TemplateResponse(request, "call_detail.html", {"call": _dump(call)})
