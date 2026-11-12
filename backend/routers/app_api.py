"""Read endpoints for the web app (see backend/views.py). One call per screen, already shaped for it.

Writes (create a patient, add a prescription, start/end a call, join an escalation) use the existing
endpoints in the other routers, and live events use the existing WebSockets.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend import views
from backend.access import require_call_owner, require_caregiver, require_patient, require_staff
from backend.db import caregivers_col, calls_col, doc_to_model, doctors_col, patients_col
from backend.live_calls import active_patient_ids
from backend.models import Call, Caregiver, Doctor, Patient

router = APIRouter(prefix="/api/app", tags=["app"])


async def _patient_data(patient_id: str) -> views.PatientData:
    data = await views.load_patient(patient_id)
    if data is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return data


@router.get("/people", response_model=views.People, dependencies=[Depends(require_staff)])
async def people() -> views.People:
    """Everyone on file (staff only: the operator's pickers)."""
    patients = [doc_to_model(Patient, d) async for d in patients_col().find()]
    doctors = [doc_to_model(Doctor, d) async for d in doctors_col().find()]
    names = {p.id: p.name for p in patients}
    # Only family contacts still linked from a patient, each shown with who they look after.
    linked = {p.caregiver_id for p in patients if p.caregiver_id}
    caregivers = [doc_to_model(Caregiver, d) async for d in caregivers_col().find({"_id": {"$in": list(linked)}})]
    return views.People(
        patients=sorted((views.person(p) for p in patients), key=lambda p: p.name.lower()),
        doctors=sorted((views.Person(id=d.id, name=d.name, description=d.description) for d in doctors),
                       key=lambda p: p.name.lower()),
        caregivers=sorted((views.Person(id=c.id, name=c.name, description=f"{names.get(c.patient_id, '?')} · {c.relation}")
                           for c in caregivers), key=lambda p: p.name.lower()),
    )


# --- patient --------------------------------------------------------------------------------

@router.get("/patients/{patient_id}/home", response_model=views.PatientHome,
            dependencies=[Depends(require_patient)])
async def patient_home(patient_id: str) -> views.PatientHome:
    return views.patient_home(await _patient_data(patient_id))


@router.get("/patients/{patient_id}/medicines", response_model=views.PatientMedicines,
            dependencies=[Depends(require_patient)])
async def patient_medicines(patient_id: str) -> views.PatientMedicines:
    return views.patient_medicines(await _patient_data(patient_id))


@router.get("/patients/{patient_id}/history", response_model=views.PatientHistory,
            dependencies=[Depends(require_patient)])
async def patient_history(patient_id: str) -> views.PatientHistory:
    return views.patient_history(await _patient_data(patient_id))


# --- caregiver ------------------------------------------------------------------------------

@router.get("/caregivers/{caregiver_id}/home", response_model=views.CaregiverHome,
            dependencies=[Depends(require_caregiver)])
async def caregiver_home(caregiver_id: str) -> views.CaregiverHome:
    caregiver = doc_to_model(Caregiver, await caregivers_col().find_one({"_id": caregiver_id}))
    if caregiver is None:
        raise HTTPException(status_code=404, detail="caregiver not found")
    data = await _patient_data(caregiver.patient_id)
    home = views.caregiver_home(data, caregiver.patient_id in set(active_patient_ids()))
    if home is None or home.caregiver.id != caregiver_id:
        raise HTTPException(status_code=404, detail="no longer the family contact for this patient")
    return home


# --- doctor ---------------------------------------------------------------------------------

@router.get("/doctors/{doctor_id}/overview", response_model=views.DoctorOverview,
            dependencies=[Depends(require_staff)])
async def doctor_overview(doctor_id: str) -> views.DoctorOverview:
    overview = await views.doctor_overview(doctor_id)
    if overview is None:
        raise HTTPException(status_code=404, detail="doctor not found")
    return overview


@router.get("/doctors/{doctor_id}/patients/{patient_id}", response_model=views.PatientClinical,
            dependencies=[Depends(require_staff)])
async def doctor_patient(doctor_id: str, patient_id: str) -> views.PatientClinical:
    doctors = [doc_to_model(Doctor, d) async for d in doctors_col().find()]
    if not any(d.id == doctor_id for d in doctors):
        raise HTTPException(status_code=404, detail="doctor not found")
    clinical = await views.patient_clinical(patient_id, {d.id: d.name for d in doctors}, doctor_id)
    if clinical is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return clinical


@router.get("/doctors/{doctor_id}/escalations/{escalation_id}", response_model=views.EscalationView,
            dependencies=[Depends(require_staff)])
async def doctor_escalation(doctor_id: str, escalation_id: str) -> views.EscalationView:
    view = await views.escalation_view(escalation_id, doctor_id)
    if view is None:
        raise HTTPException(status_code=404, detail="call not found")
    return view


# --- shared ---------------------------------------------------------------------------------

@router.get("/calls/{call_id}", response_model=views.CallTranscript, dependencies=[Depends(require_call_owner)])
async def call_transcript(call_id: str) -> views.CallTranscript:
    call = doc_to_model(Call, await calls_col().find_one({"_id": call_id}))
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    patient = doc_to_model(Patient, await patients_col().find_one({"_id": call.patient_id}))
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return views.call_transcript(call, patient)


# --- operator -------------------------------------------------------------------------------

@router.get("/operator/roster", response_model=views.OperatorRoster, dependencies=[Depends(require_staff)])
async def operator_roster() -> views.OperatorRoster:
    return await views.operator_roster(set(active_patient_ids()))


@router.get("/operator/patients/{patient_id}", response_model=views.PatientClinical,
            dependencies=[Depends(require_staff)])
async def operator_patient(patient_id: str) -> views.PatientClinical:
    """The same clinical picture a doctor gets, for hospital staff (no doctor is the viewer)."""
    doctors = [doc_to_model(Doctor, d) async for d in doctors_col().find()]
    clinical = await views.patient_clinical(patient_id, {d.id: d.name for d in doctors}, None)
    if clinical is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return clinical
