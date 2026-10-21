"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { api, ApiError, useApi } from "@/lib/api";
import type { People, PatientProfile } from "@/lib/types";

/** Add a patient (no `patient`) or edit one. Both send the same fields. */
export function PatientForm({ patient }: { patient?: PatientProfile }) {
  const router = useRouter();
  const { data: people } = useApi<People>("/api/app/people", 60_000);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [doctorIds, setDoctorIds] = useState<string[]>(patient?.doctor_ids ?? []);
  const cg = patient?.caregiver;
  const back = patient ? `/operator/patients/${patient.id}` : "/operator";

  return (
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
          await api(patient ? `/api/patients/${patient.id}` : "/api/patients", {
            method: patient ? "PATCH" : "POST",
            json: {
              name: s("name"), age: Number(s("age")), phone_number: s("phone_number"),
              address: s("address") || null, description: s("description") || null,
              allergies: s("allergies").split(",").map((a) => a.trim()).filter(Boolean),
              caregiver: s("caregiver_name")
                ? { name: s("caregiver_name"), relation: s("caregiver_relation") || "family", phone_number: s("caregiver_phone") }
                : null,
              doctor_ids: doctorIds,
            },
          });
          router.push(back);
        } catch (err) {
          setError(err instanceof ApiError ? err.message : "Could not save the patient");
          setBusy(false);
        }
      }}
    >
      <section className="card stack">
        <h2>Patient</h2>
        <div className="form-grid">
          <div className="field"><label htmlFor="name">Full name</label><input id="name" name="name" type="text" required autoComplete="off" placeholder="e.g. Asha Verma" defaultValue={patient?.name} /></div>
          <div className="field"><label htmlFor="age">Age</label><input id="age" name="age" type="number" inputMode="numeric" min={0} max={120} required defaultValue={patient?.age} /></div>
          <div className="field"><label htmlFor="phone">Phone number</label><input id="phone" name="phone_number" type="tel" required autoComplete="off" spellCheck={false} placeholder="+91 98765 43210" defaultValue={patient?.phone_number} /></div>
          <div className="field"><label htmlFor="address">Address</label><input id="address" name="address" type="text" autoComplete="off" defaultValue={patient?.address ?? ""} /></div>
        </div>
        <div className="field"><label htmlFor="allergies">Allergies</label><input id="allergies" name="allergies" type="text" placeholder="Penicillin, Aspirin…" autoComplete="off" defaultValue={patient?.allergies.join(", ")} /><span className="hint">Comma separated. Leave empty if none are known.</span></div>
        <div className="field"><label htmlFor="desc">Notes</label><textarea id="desc" name="description" rows={2} placeholder="Conditions, anything the doctor should know…" defaultValue={patient?.description ?? ""} /></div>
      </section>

      <section className="card stack">
        <div><h2>Doctors</h2><p className="small muted">These doctors are rung when the patient needs one. With none assigned, an escalation reaches nobody.</p></div>
        {!people ? <p className="small muted">Loading doctors…</p> : people.doctors.length === 0 ? <p className="small muted">No doctors exist yet.</p> : (
          <div className="stack" style={{ gap: 8 }}>
            {people.doctors.map((d) => (
              <label key={d.id} className="row" style={{ gap: 10 }}>
                <input
                  type="checkbox"
                  checked={doctorIds.includes(d.id)}
                  onChange={(e) => setDoctorIds((cur) => (e.target.checked ? [...cur, d.id] : cur.filter((x) => x !== d.id)))}
                />
                <span><strong>{d.name}</strong>{d.description ? <span className="muted"> · {d.description}</span> : null}</span>
              </label>
            ))}
          </div>
        )}
      </section>

      <section className="card stack">
        <div><h2>Family contact</h2><p className="small muted">Told if the patient can&apos;t be reached or needs a doctor. Optional{patient ? "; clear the name to remove them" : ""}.</p></div>
        <div className="form-grid">
          <div className="field"><label htmlFor="cg-name">Name</label><input id="cg-name" name="caregiver_name" type="text" autoComplete="off" defaultValue={cg?.name} /></div>
          <div className="field"><label htmlFor="cg-rel">Relation</label><input id="cg-rel" name="caregiver_relation" type="text" placeholder="son, daughter, spouse…" autoComplete="off" defaultValue={cg?.relation} /></div>
          <div className="field"><label htmlFor="cg-phone">Phone number</label><input id="cg-phone" name="caregiver_phone" type="tel" autoComplete="off" spellCheck={false} defaultValue={cg?.phone_number} /></div>
        </div>
      </section>

      {error && <div className="callout crit" role="alert"><Icon name="alert" /><p>{error}</p></div>}
      <div className="row">
        <button className="btn" type="submit" disabled={busy}>{busy ? "Saving…" : patient ? "Save changes" : "Add Patient"}</button>
        <Link href={back} className="btn ghost">Cancel</Link>
      </div>
    </form>
  );
}
