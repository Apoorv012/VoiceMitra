"use client";

import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ago } from "@/lib/format";
import type { AdherenceView, EscalationRow } from "@/lib/types";

const DAY_LABEL: Record<string, string> = {
  good: "all doses taken", mixed: "some doses missed", missed: "doses missed",
  unknown: "no check-in", upcoming: "later", none: "nothing scheduled",
};

/** Seven small dots, oldest first. Supplementary to the numbers beside it, so it carries a text label. */
export function WeekDots({ states }: { states: string[] }) {
  const summary = states.map((s) => DAY_LABEL[s] ?? s).join(", ");
  return (
    <span className="dots" role="img" aria-label={`Last 7 days: ${summary}`} title={summary}>
      {states.map((s, i) => <span key={i} className={`dot sm ${s}`} />)}
    </span>
  );
}

export function Adherence({ a, compact = false }: { a: AdherenceView; compact?: boolean }) {
  if (a.rate === null) return <span className="muted small">No data yet</span>;
  const tone = a.rate >= 80 ? "good" : a.rate >= 50 ? "warn" : "crit";
  return (
    <span className="adh">
      <strong className="num">{a.rate}%</strong>
      {!compact && <span className="small muted"> · {a.taken} of {a.taken + a.missed}</span>}
      <span className={`meter ${tone}`} style={{ width: compact ? 56 : 80, display: "inline-block", marginLeft: 8, verticalAlign: "middle" }}>
        <span style={{ width: `${a.rate}%` }} />
      </span>
    </span>
  );
}

export function EscalationStatus({ status }: { status: string }) {
  switch (status) {
    case "ringing": return <span className="chip crit"><Icon name="phone" />Ringing</span>;
    case "briefing": return <span className="chip warn"><Icon name="clock" />Doctor being briefed</span>;
    case "merged": return <span className="chip warn"><Icon name="phone" />On the call</span>;
    case "resolved": return <span className="chip good"><Icon name="check" />Resolved</span>;
    default: return <span className="chip"><Icon name="x" />Not connected</span>;
  }
}

export function EscalationList({
  rows, doctorId, showPatient = true,
}: { rows: EscalationRow[]; doctorId?: string; showPatient?: boolean }) {
  return (
    <ul className="list">
      {rows.map((e) => {
        const live = (e.status === "briefing" || e.status === "merged") && e.is_mine && doctorId;
        return (
          <li key={e.id} style={{ alignItems: "flex-start" }}>
            <div className="grow">
              <div className="row wrap" style={{ gap: 8 }}>
                {showPatient && <strong>{e.patient_name}</strong>}
                <EscalationStatus status={e.status} />
                <span className="tiny muted">{ago(e.created_at)}</span>
              </div>
              <p className="small ink-2" style={{ marginTop: 4 }}>{e.reason}</p>
              {e.summary && <p className="small muted" style={{ marginTop: 4, whiteSpace: "pre-wrap" }}>{e.summary}</p>}
            </div>
            <div className="stack-sm" style={{ alignItems: "flex-end" }}>
              {live && <Link className="btn sm good" href={`/doctors/${doctorId}/escalations/${e.id}`}>Open live call</Link>}
              <Link className="btn ghost sm" href={`/calls/${e.call_id}`}>Call log</Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
