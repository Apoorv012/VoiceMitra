"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { PatientForm } from "@/components/staff/PatientForm";
import { ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { PatientProfile } from "@/lib/types";

export default function EditPatient() {
  const { id } = useParams<{ id: string }>();
  // No polling or refocus refresh: it must not replace what is being typed.
  const { data, error, mutate } = useApi<PatientProfile>(`/api/patients/${id}/profile`, 0, { revalidateOnFocus: false });
  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;
  return (
    <>
      <Link href={`/operator/patients/${id}`} className="crumb"><Icon name="chevron-left" />{data.name}</Link>
      <h1>Edit patient</h1>
      <PatientForm patient={data} />
    </>
  );
}
