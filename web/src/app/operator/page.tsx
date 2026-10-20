"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { Icon } from "@/components/Icon";
import { AttentionChip, Avatar, ErrorState, Loading } from "@/components/ui";
import { api, ApiError, useApi } from "@/lib/api";
import type { OperatorEvent } from "@/lib/events";
import { ago } from "@/lib/format";
import type { OperatorRoster } from "@/lib/types";
import { useSocket } from "@/lib/ws";

const STATUS: Record<string, [string, string]> = { good: ["good", "Good"], remedy: ["warn", "Remedy"], urgent: ["crit", "Urgent"] };

export default function Roster() {
  const { data, error, mutate } = useApi<OperatorRoster>("/api/app/operator/roster", 30_000);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  // Calls start and end on the server; the socket tells us so the roster is always current.
  useSocket<OperatorEvent>("/ws/operator", useCallback(() => { void mutate(); }, [mutate]));

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const act = async (patientId: string, path: "voice-call" | "call" | "call/end") => {
    setBusy(patientId + path);
    setProblem(null);
    try {
      await api(`/api/patients/${patientId}/${path}`, { method: "POST" });
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : "That didn't work");
    } finally {
      setBusy(null);
      void mutate();
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Patients</h1>
          <p className="ink-2">{data.patients.length} registered · start a check-in call or open a record.</p>
        </div>
        <Link href="/operator/patients/new" className="btn"><Icon name="plus" />Add patient</Link>
      </div>

      {problem && <div className="callout crit" role="alert"><Icon name="alert" /><p>{problem}</p></div>}

      <div className="card flush">
        {data.patients.length === 0 ? <p className="empty">No patients yet. Add the first one.</p> : (
          <ul className="list">
            {data.patients.map((p) => {
              const [tone, label] = (p.last_status && STATUS[p.last_status]) || ["", p.last_call_at ? "Pending" : "No calls yet"];
              return (
                <li key={p.id} style={{ flexWrap: "wrap" }}>
                  <Avatar name={p.name} />
                  <Link href={`/operator/patients/${p.id}`} className="grow" style={{ color: "inherit", minWidth: 180 }}>
                    <strong>{p.name}</strong> <span className="muted small">{p.age} · {p.phone_number}</span>
                    <span className="small muted" style={{ display: "block" }}>{p.last_call_at ? `Last call ${ago(p.last_call_at)}` : "Never called"}</span>
                  </Link>
                  <span className={`chip ${tone}`}>{label}</span>
                  <AttentionChip level={p.attention.level} />
                  <span className="row" style={{ gap: 8 }}>
                    {p.in_call ? (
                      <>
                        <span className="chip warn"><Icon name="phone" />In call</span>
                        <button type="button" className="btn secondary sm" disabled={busy === p.id + "call/end"} onClick={() => void act(p.id, "call/end")}>End call</button>
                      </>
                    ) : (
                      <>
                        <button type="button" className="btn sm" disabled={!!busy} onClick={() => void act(p.id, "voice-call")}><Icon name="mic" />Voice call</button>
                        <button type="button" className="btn secondary sm" disabled={!!busy} onClick={() => void act(p.id, "call")}>Chat call</button>
                      </>
                    )}
                    <a className="btn ghost sm" href={`/patients/${p.id}?preview=1`} target="_blank" rel="noopener" title="Open this patient's app in a new tab">Patient app ↗</a>
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </>
  );
}
