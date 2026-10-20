"use client";

import { useParams } from "next/navigation";
import { PatientClinicalView } from "@/components/staff/PatientClinicalView";
import { ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { PatientClinical } from "@/lib/types";

export default function DoctorPatient() {
  const { id, pid } = useParams<{ id: string; pid: string }>();
  const { data, error, mutate } = useApi<PatientClinical>(`/api/app/doctors/${id}/patients/${pid}`, 30_000);
  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;
  return <PatientClinicalView data={data} base={`/doctors/${id}`} doctorId={id} onChanged={() => void mutate()} />;
}
