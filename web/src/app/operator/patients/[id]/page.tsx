"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { LoginAdmin } from "@/components/staff/LoginAdmin";
import { PatientClinicalView } from "@/components/staff/PatientClinicalView";
import { ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import type { PatientClinical } from "@/lib/types";

type PatientProfile = components["schemas"]["PatientProfile"];

export default function ManagePatient() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientClinical>(`/api/app/operator/patients/${id}`, 30_000);
  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;
  return (
    <>
      <PatientClinicalView data={data} base="/operator" onChanged={() => void mutate()} />
      <Logins patientId={id} />
    </>
  );
}

/** Who can sign in for this patient: the patient (website + phone app) and the family contact (website). */
function Logins({ patientId }: { patientId: string }) {
  const { data: profile } = useApi<PatientProfile>(`/api/patients/${patientId}/profile`, 0);
  return (
    <section id="logins" className="stack-sm">
      <h2>Sign-in logins</h2>
      <p className="small ink-2">
        Nobody can sign up on their own: you set each login here and pass it on (by phone or WhatsApp).
      </p>
      {!profile ? <Loading /> : (
        <div className="tiles" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
          <LoginAdmin
            url={`/api/patients/${patientId}/login`}
            title={`Patient: ${profile.name}`}
            sub="Signs in on the website and in the VoiceMitra phone app (the same login)."
            personName={profile.name}
          />
          {profile.caregiver && profile.caregiver_id ? (
            <LoginAdmin
              url={`/api/caregivers/${profile.caregiver_id}/login`}
              title={`Family: ${profile.caregiver.name} (${profile.caregiver.relation})`}
              sub="Signs in on the website only, to see alerts and how the patient is doing."
              personName={profile.caregiver.name}
            />
          ) : (
            <div className="card">
              <h3>Family</h3>
              <p className="small ink-2" style={{ margin: "4px 0 12px" }}>No family contact on file.</p>
              <Link href={`/operator/patients/${patientId}/edit`} className="btn ghost sm">Add one in Edit details</Link>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
