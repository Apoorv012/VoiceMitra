"use client";

import { useParams } from "next/navigation";
import { PatientClinicalView } from "@/components/staff/PatientClinicalView";
import { ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { PatientClinical } from "@/lib/types";

export default function ManagePatient() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientClinical>(`/api/app/operator/patients/${id}`, 30_000);
  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;
  return <PatientClinicalView data={data} base="/operator" onChanged={() => void mutate()} />;
}
