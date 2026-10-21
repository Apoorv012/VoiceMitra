"use client";

import Link from "next/link";
import { Icon } from "@/components/Icon";
import { PatientForm } from "@/components/staff/PatientForm";

export default function NewPatient() {
  return (
    <>
      <Link href="/operator" className="crumb"><Icon name="chevron-left" />Patients</Link>
      <h1>Add a Patient</h1>
      <PatientForm />
    </>
  );
}
