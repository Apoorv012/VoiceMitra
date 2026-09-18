"""Fixture data for the demo: patient "Apoorv" (matches reference_transcripts/), a doctor,
a caregiver, and a PCM 500 prescription. Run with: python -m backend.seed
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

from backend.db import (
    calls_col,
    caregivers_col,
    daily_logs_col,
    doctors_col,
    dose_events_col,
    ensure_indexes,
    model_to_doc,
    patients_col,
    prescriptions_col,
)
from backend.models import (
    Caregiver,
    Doctor,
    DoseFrequency,
    Dosage,
    Patient,
    Prescription,
)


async def seed() -> None:
    await ensure_indexes()

    # Wipe existing demo data so the script is re-runnable.
    for col in (patients_col(), caregivers_col(), prescriptions_col(), dose_events_col(), doctors_col(), calls_col(), daily_logs_col()):
        await col.delete_many({})

    doctor = Doctor(
        name="Dr. Mehta",
        age=45,
        description="General physician",
        phone_number="+919800000001",
        address="Apollo Clinic, Delhi",
    )

    patient = Patient(
        name="Apoorv",
        age=21,
        description="No known chronic conditions",
        phone_number="+919800000002",
        address="Delhi",
        allergies=[],
    )

    caregiver = Caregiver(
        patient_id=patient.id,
        name="Rakesh (father)",
        relation="father",
        phone_number="+919800000003",
    )
    patient.caregiver_id = caregiver.id

    prescription = Prescription(
        patient_id=patient.id,
        medicines=[
            Dosage(
                prescription_id="",  # set below
                medicine_name="PCM 500",
                dosage="1 tablet",
                from_date=date.today(),
                to_date=date.today() + timedelta(days=14),
                frequency=DoseFrequency.fixed_times,
                times=["09:00", "21:00"],
            )
        ],
    )
    for m in prescription.medicines:
        m.prescription_id = prescription.id
    patient.prescription_ids.append(prescription.id)

    doctor.patient_ids.append(patient.id)

    await doctors_col().insert_one(model_to_doc(doctor))
    await caregivers_col().insert_one(model_to_doc(caregiver))
    await prescriptions_col().insert_one(model_to_doc(prescription))
    await patients_col().insert_one(model_to_doc(patient))

    print(f"Seeded patient {patient.name} ({patient.id})")
    print(f"Seeded doctor {doctor.name} ({doctor.id})")
    print(f"Seeded caregiver {caregiver.name} ({caregiver.id})")
    print(f"Seeded prescription {prescription.id} with dosage {prescription.medicines[0].medicine_name}")


if __name__ == "__main__":
    asyncio.run(seed())
