"use client";

import { useEffect, type ReactNode } from "react";
import { StaffShell } from "@/components/staff/StaffShell";
import { setIdentity } from "@/lib/identity";

export default function OperatorLayout({ children }: { children: ReactNode }) {
  useEffect(() => setIdentity({ role: "operator" }), []);
  return (
    <StaffShell
      nav={[
        { href: "/operator", label: "Patients", icon: "users", match: (p) => p === "/operator" || (p.startsWith("/operator/patients/") && !p.endsWith("/new")) },
        { href: "/operator/patients/new", label: "Add patient", icon: "plus" },
      ]}
      name="Hospital staff"
      role="Operator"
    >
      {children}
    </StaffShell>
  );
}
