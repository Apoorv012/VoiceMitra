"use client";

import { useParams } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { setIdentity } from "@/lib/identity";

/** The caregiver's app: one screen about the patient they look after, in the patient app's look. */
export default function CaregiverLayout({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();

  // Same as the patient app: opening the link on a device remembers who this is (?preview=1 doesn't).
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has("preview")) setIdentity({ role: "caregiver", id });
  }, [id]);

  return (
    <div className="phone patient-app">
      <header className="p-head">
        <span className="row" style={{ gap: 10 }}>
          <span className="brand-mark" style={{ width: 36, height: 36, borderRadius: 12 }}><Icon name="mic" /></span>
          <strong translate="no">VoiceMitra</strong>
        </span>
        <LangSwitch />
      </header>
      <main className="p-main">{children}</main>
    </div>
  );
}
