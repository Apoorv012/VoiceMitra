"use client";

import { useParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Ringing } from "@/components/staff/Ringing";
import { StaffShell } from "@/components/staff/StaffShell";
import { useApi } from "@/lib/api";
import { setIdentity } from "@/lib/identity";
import type { DoctorOverview } from "@/lib/types";

export default function DoctorLayout({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const { data } = useApi<DoctorOverview>(`/api/app/doctors/${id}/overview`, 30_000);

  useEffect(() => setIdentity({ role: "doctor", id }), [id]);

  return (
    <StaffShell
      nav={[{ href: `/doctors/${id}`, label: "Overview", icon: "home", match: (p) => !p.includes("/calls/") }]}
      name={data?.doctor.name ?? "Doctor"}
      role="Doctor"
    >
      <Ringing doctorId={id} />
      {children}
    </StaffShell>
  );
}
