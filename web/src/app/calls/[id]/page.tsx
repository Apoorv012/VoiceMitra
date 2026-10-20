"use client";

import { useParams, useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { when } from "@/lib/format";
import { useIdentity } from "@/lib/identity";
import { useT } from "@/lib/i18n";
import type { CallTranscript, TranscriptEntry } from "@/lib/types";

const LEG: Record<string, string> = { doctor_briefing: "Doctor briefing (patient on hold)", merged: "Doctor + patient" };

function Entry({ e, staff, tz }: { e: TranscriptEntry; staff: boolean; tz: string }) {
  const { t } = useT();
  const time = when(e.at, tz, "en");
  const leg = staff && e.leg ? LEG[e.leg] ?? e.leg : null;

  if (e.kind === "tool") {
    if (!staff) return null;
    return (
      <details className="small muted" style={{ alignSelf: "center", maxWidth: "92%" }}>
        <summary style={{ cursor: "pointer" }}>Tool: {e.tool_name}{e.note ? ` · ${e.note}` : ""}</summary>
        <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.78rem", margin: "6px 0 0" }}>
          {JSON.stringify({ args: e.tool_args, result: e.tool_result }, null, 2)}
        </pre>
      </details>
    );
  }
  if (e.kind === "event") return staff ? <div className="bubble note">{e.text}</div> : null;
  if (e.kind === "summary") {
    if (!staff) return null;
    return (
      <div className="callout good" style={{ whiteSpace: "pre-wrap" }}>
        <Icon name="file" />
        <div><p className="strong">Summary of the doctor–patient call</p><p>{e.text}</p></div>
      </div>
    );
  }
  if (e.leg === "doctor_briefing" && !staff) return null; // the doctor's private chat with the agent

  const cls = staff
    ? e.kind === "patient" ? "bubble patient" : e.kind === "doctor" ? "bubble doctor" : "bubble"
    : e.kind === "patient" ? "bubble me" : e.kind === "doctor" ? "bubble doctor" : "bubble";
  const who = staff ? (e.kind === "patient" ? "Patient" : e.kind === "doctor" ? "Doctor" : "VoiceMitra")
    : e.kind === "doctor" ? "Doctor" : e.kind === "agent" ? t("agent_said") : t("you_said");
  return (
    <div className={cls} title={time}>
      <div className="who">{who}{leg ? ` · ${leg}` : ""}</div>
      {e.text}
    </div>
  );
}

export default function CallPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const identity = useIdentity();
  const { t, lang } = useT();
  const { data, error, mutate } = useApi<CallTranscript>(`/api/app/calls/${id}`, 0);
  const staff = identity?.role === "doctor" || identity?.role === "operator";

  return (
    <main className="phone patient-app" style={{ paddingBottom: 32 }}>
      <header className="p-head">
        <button type="button" className="btn ghost sm" onClick={() => router.back()}><Icon name="chevron-left" />Back</button>
      </header>
      <div className="p-main">
        {error && !data ? <ErrorState onRetry={() => mutate()} /> : !data ? <Loading /> : (
          <>
            <div>
              <h1>{t("transcript_title")}</h1>
              <p className="ink-2 small">{data.patient.name} · {when(data.at, data.timezone, lang)}</p>
            </div>
            {staff && data.escalation_reason && (
              <div className="callout crit"><Icon name="alert" /><div><p className="strong">Escalated</p><p>{data.escalation_reason}{data.caregiver_notified ? " · caregiver notified" : ""}</p></div></div>
            )}
            <div className="card">
              {data.entries.length === 0 ? (
                <p className="muted">{t("transcript_empty")}</p>
              ) : (
                <div className="chat">
                  {data.entries.map((e, i) => <Entry key={i} e={e} staff={staff} tz={data.timezone} />)}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}
