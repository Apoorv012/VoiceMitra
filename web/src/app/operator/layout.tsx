"use client";

import type { ReactNode } from "react";
import { StaffShell } from "@/components/staff/StaffShell";
import { RequireSignIn } from "@/components/RequireSignIn";
import { useIdentity } from "@/lib/identity";

export default function OperatorLayout({ children }: { children: ReactNode }) {
  const me = useIdentity();
  return (
    <RequireSignIn allow={(m) => m.role === "staff"}>
    <StaffShell
      nav={[
        { href: "/operator", label: "Patients", icon: "users", match: (p) => p === "/operator" || (p.startsWith("/operator/patients/") && !p.endsWith("/new")) },
        { href: "/operator/patients/new", label: "Add patient", icon: "plus" },
        { href: "/operator/messages", label: "Messages", icon: "send" },
      ]}
      name={me?.name ?? "Staff"}
      role="Staff"
    >
      {children}
    </StaffShell>
    </RequireSignIn>
  );
}
