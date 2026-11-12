"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { Ringing } from "@/components/staff/Ringing";
import { StaffShell } from "@/components/staff/StaffShell";
import { useApi } from "@/lib/api";
import { RequireSignIn } from "@/components/RequireSignIn";
import type { DoctorOverview } from "@/lib/types";

// Staff only for now: the doctor flow is off for the pilot and doctors have no logins yet.
export default function DoctorLayout({ children }: { children: ReactNode }) {
  return (
    <RequireSignIn allow={(me) => me.role === "staff"}>
      <DoctorShell>{children}</DoctorShell>
    </RequireSignIn>
  );
}

function DoctorShell({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const { data } = useApi<DoctorOverview>(`/api/app/doctors/${id}/overview`, 30_000);

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
