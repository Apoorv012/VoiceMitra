"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { api, ApiError } from "@/lib/api";

export default function NewPatient() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <>
      <Link href="/operator" className="crumb"><Icon name="chevron-left" />Patients</Link>
      <h1>Add a patient</h1>
      <form
        className="stack"
        style={{ maxWidth: 640 }}
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          const s = (k: string) => String(f.get(k) ?? "").trim();
          setBusy(true);
          setError(null);
          try {
            await api("/api/patients", {
              method: "POST",
              json: {
                name: s("name"), age: Number(s("age")), phone_number: s("phone_number"),
                address: s("address") || null, description: s("description") || null,
                allergies: s("allergies").split(",").map((a) => a.trim()).filter(Boolean),
                caregiver: s("caregiver_name")
                  ? { name: s("caregiver_name"), relation: s("caregiver_relation") || "family", phone_number: s("caregiver_phone") }
                  : null,
              },
            });
            router.push("/operator");
          } catch (err) {
            setError(err instanceof ApiError ? err.message : "Could not add the patient");
            setBusy(false);
          }
        }}
      >
        <section className="card stack">
          <h2>Patient</h2>
          <div className="form-grid">
            <div className="field"><label htmlFor="name">Full name</label><input id="name" name="name" type="text" required autoComplete="off" /></div>
            <div className="field"><label htmlFor="age">Age</label><input id="age" name="age" type="number" min={0} max={120} required /></div>
            <div className="field"><label htmlFor="phone">Phone number</label><input id="phone" name="phone_number" type="tel" required /></div>
            <div className="field"><label htmlFor="address">Address</label><input id="address" name="address" type="text" /></div>
          </div>
          <div className="field"><label htmlFor="allergies">Allergies</label><input id="allergies" name="allergies" type="text" placeholder="Penicillin, Aspirin" /><span className="hint">Comma separated. Leave empty if none are known.</span></div>
          <div className="field"><label htmlFor="desc">Notes</label><textarea id="desc" name="description" rows={2} placeholder="Conditions, anything the doctor should know" /></div>
        </section>

        <section className="card stack">
          <div><h2>Family contact</h2><p className="small muted">Told if the patient can&apos;t be reached or needs a doctor. Optional.</p></div>
          <div className="form-grid">
            <div className="field"><label htmlFor="cg-name">Name</label><input id="cg-name" name="caregiver_name" type="text" /></div>
            <div className="field"><label htmlFor="cg-rel">Relation</label><input id="cg-rel" name="caregiver_relation" type="text" placeholder="son, daughter, spouse" /></div>
            <div className="field"><label htmlFor="cg-phone">Phone number</label><input id="cg-phone" name="caregiver_phone" type="tel" /></div>
          </div>
        </section>

        {error && <div className="callout crit" role="alert"><Icon name="alert" /><p>{error}</p></div>}
        <div className="row">
          <button className="btn" type="submit" disabled={busy}>{busy ? "Adding…" : "Add patient"}</button>
          <Link href="/operator" className="btn ghost">Cancel</Link>
        </div>
      </form>
    </>
  );
}
