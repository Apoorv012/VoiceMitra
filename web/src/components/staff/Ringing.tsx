"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { useSWRConfig } from "swr";
import { Icon } from "@/components/Icon";
import { api, ApiError } from "@/lib/api";
import type { DoctorEvent, RingEvent } from "@/lib/events";
import { useSocket } from "@/lib/ws";

type Ring = RingEvent;

/**
 * Incoming escalated calls, pushed over the doctor's socket: a card rings until someone joins or the
 * call ends. Lives in the doctor layout so a call can be picked up from any screen.
 */
export function Ringing({ doctorId }: { doctorId: string }) {
  const router = useRouter();
  const { mutate } = useSWRConfig();
  const [rings, setRings] = useState<Ring[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const onEvent = useCallback((e: DoctorEvent) => {
    if (e.type === "snapshot") setRings(e.ringing ?? []);
    else if (e.type === "incoming_call") setRings((r) => (r.some((x) => x.escalation_id === e.escalation_id) ? r : [...r, e]));
    else if (e.type === "call_taken" || e.type === "call_ended") {
      setRings((r) => r.filter((x) => x.escalation_id !== e.escalation_id));
      if (e.type === "call_ended") void mutate(`/api/app/doctors/${doctorId}/overview`); // the lists below change
    }
  }, [doctorId, mutate]);

  useSocket<DoctorEvent>(`/ws/doctors/${doctorId}`, onEvent);

  const join = async (ring: Ring) => {
    setBusy(ring.escalation_id);
    setErrors((e) => ({ ...e, [ring.escalation_id]: "" }));
    try {
      const { url } = await api<{ url: string }>(`/api/escalations/${ring.escalation_id}/join`, {
        method: "POST",
        json: { doctor_id: doctorId },
      });
      router.push(url);
    } catch (err) {
      setBusy(null);
      setErrors((e) => ({ ...e, [ring.escalation_id]: err instanceof ApiError ? err.message : "Could not join" }));
    }
  };

  if (rings.length === 0) return null;
  return (
    <div className="stack-sm" role="alert" aria-live="assertive">
      {rings.map((r) => (
        <div key={r.escalation_id} className="ringing">
          <span className="pulse warm"><span className="avatar crit"><Icon name="phone" /></span></span>
          <div className="grow">
            <strong>Incoming call — {r.patient_name}</strong>
            <p className="small">An escalated check-in is on hold. VoiceMitra will brief you before you speak to the patient.</p>
            {errors[r.escalation_id] && <p className="small strong">{errors[r.escalation_id]}</p>}
          </div>
          <button type="button" className="btn good" disabled={busy === r.escalation_id} onClick={() => void join(r)}>
            {busy === r.escalation_id ? "Joining…" : "Join call"}
          </button>
        </div>
      ))}
    </div>
  );
}
