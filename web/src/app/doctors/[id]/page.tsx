"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Adherence, EscalationList, WeekDots } from "@/components/staff/parts";
import { AttentionChip, Avatar, ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import type { DoctorOverview, PatientRow } from "@/lib/types";

function AttentionCard({ row, doctorId }: { row: PatientRow; doctorId: string }) {
  const critical = row.attention.level === "critical";
  return (
    <Link href={`/doctors/${doctorId}/patients/${row.id}`} className="card attn-card" style={critical ? { borderColor: "var(--crit)" } : undefined}>
      <div className="row top">
        <Avatar name={row.name} tone={critical ? "crit" : "warn"} />
        <div className="grow">
          <div className="row wrap" style={{ gap: 8 }}>
            <strong style={{ fontSize: "1.05rem" }}>{row.name}</strong>
            <span className="muted small">{row.age}</span>
            <AttentionChip level={row.attention.level} />
          </div>
          <ul className="reasons">
            {row.attention.reasons.slice(0, 3).map((r) => <li key={r}>{r}</li>)}
          </ul>
        </div>
        <Icon name="chevron-right" className="chev" />
      </div>
      <div className="row between wrap" style={{ marginTop: 12, paddingLeft: 56 }}>
        <Adherence a={row.adherence} compact />
        <WeekDots states={row.week} />
        <span className="tiny muted">{row.last_checkin_at ? `Last check-in ${ago(row.last_checkin_at)}` : "No check-ins yet"}</span>
      </div>
    </Link>
  );
}

export default function DoctorHome() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<DoctorOverview>(`/api/app/doctors/${id}/overview`, 30_000);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const attention = data.patients.filter((p) => p.attention.level !== "ok");
  const stable = data.patients.filter((p) => p.attention.level === "ok");
  const t = data.tiles;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{data.doctor.name}</h1>
          <p className="ink-2 hero-sub">{data.doctor.description || "Patients who need you, and how everyone else is doing."}</p>
        </div>
        <p className="small muted page-date">{new Intl.DateTimeFormat("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date())}</p>
      </div>

      <div className="tiles">
        <div className="tile">
          <span className="tile-ico"><Icon name="users" /></span>
          <span className="label">Patients</span><span className="value">{t.patients}</span>
        </div>
        <div className={`tile ${t.needing_attention ? "attn" : ""}`}>
          <span className="tile-ico"><Icon name="alert" /></span>
          <span className="label">Need attention</span>
          <span className="value">{t.needing_attention}</span>
          <span className="sub">{t.needing_attention ? "Reviewed below" : "All clear"}</span>
        </div>
        <div className="tile">
          <span className="tile-ico"><Icon name="phone" /></span>
          <span className="label">Check-ins today</span><span className="value">{t.checkins_today}</span>
        </div>
        <div className="tile">
          <span className="tile-ico"><Icon name="activity" /></span>
          <span className="label">Adherence, last 7 days</span>
          <span className="value">{t.adherence_rate === null ? "—" : <>{t.adherence_rate}<small>%</small></>}</span>
          <span className="sub">Of doses we heard about</span>
        </div>
      </div>

      <section className="stack-sm">
        <h2>Needs attention</h2>
        {attention.length === 0 ? (
          <div className="callout good"><Icon name="check" /><p>No one needs a doctor&apos;s attention right now.</p></div>
        ) : (
          attention.map((p) => <AttentionCard key={p.id} row={p} doctorId={id} />)
        )}
      </section>

      {stable.length > 0 && (
        <section className="stack-sm">
          <h2>Stable</h2>
          <div className="card flush">
            <ul className="list">
              {stable.map((p) => (
                <li key={p.id}>
                  <Link href={`/doctors/${id}/patients/${p.id}`} className="list-item" style={{ padding: 0, border: 0, width: "100%" }}>
                    <Avatar name={p.name} size="sm" />
                    <span className="grow"><strong>{p.name}</strong> <span className="muted small">{p.age}</span></span>
                    <span className="hide-sm"><WeekDots states={p.week} /></span>
                    <span style={{ textAlign: "right", whiteSpace: "nowrap" }}><Adherence a={p.adherence} compact /></span>
                    <Icon name="chevron-right" className="chev" />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      <section className="stack-sm">
        <h2>Recent escalations</h2>
        <div className="card flush">
          {data.escalations.length === 0
            ? <p className="empty">No escalations yet.</p>
            : <EscalationList rows={data.escalations} doctorId={id} />}
        </div>
      </section>
    </>
  );
}
