"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { DayDot, Empty, ErrorState, Loading, SlotChip, WeekLegend } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { CaregiverEvent } from "@/lib/events";
import { dayLabel, isToday, timeOf, weekdayOf, when } from "@/lib/format";
import { clearIdentity } from "@/lib/identity";
import { useT } from "@/lib/i18n";
import type { AlertView, CaregiverHome } from "@/lib/types";
import { useSocket } from "@/lib/ws";

export default function CaregiverPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t, lang } = useT();
  const { data, error, mutate } = useApi<CaregiverHome>(`/api/app/caregivers/${id}/home`, 60_000);
  const [busy, setBusy] = useState<string | null>(null);

  // Every event means the view changed: a new alert, a call starting or ending, alerts seen on another
  // device -- and the snapshot on (re)connect, which also covers anything missed while disconnected.
  useSocket<CaregiverEvent>(`/ws/caregivers/${id}`, () => void mutate());

  const unseen = data?.unseen ?? 0;
  useEffect(() => {
    document.title = unseen > 0 ? `(${unseen}) VoiceMitra` : "VoiceMitra";
  }, [unseen]);

  if (error && !data) {
    return error.status === 404 ? <Empty icon="users">{t("cg_not_linked")}</Empty> : <ErrorState onRetry={() => mutate()} />;
  }
  if (!data) return <Loading />;

  const tz = data.timezone;
  const patientFirst = data.patient.name.split(" ")[0];
  const fresh = data.alerts.filter((a) => !a.seen_at);
  const seen = data.alerts.filter((a) => a.seen_at);
  const a = data.adherence;
  const total = a.taken + a.missed + a.unrecorded;
  const anyScheduled = data.week.some((d) => d.state !== "none");

  const markSeen = async (alertId: string | null) => {
    setBusy(alertId ?? "all");
    try {
      await api(`/api/caregivers/${id}/alerts/${alertId ? `${alertId}/` : ""}seen`, { method: "POST" });
      await mutate();
    } finally {
      setBusy(null);
    }
  };

  const label = (al: AlertView) =>
    al.urgent ? t("cg_urgent") : al.trigger === "unreachable" ? t("cg_unreachable") : t("cg_unwell");

  return (
    <>
      <section className="hello">
        <p className="eyebrow">{t("cg_looking_after", { name: data.patient.name })}</p>
        <h1>{t("namaste", { name: data.caregiver.name.split(" ")[0] })}</h1>
      </section>

      {data.in_call && (
        <section className="callout accent" role="status">
          <Icon name="phone" />
          <p>{t("cg_in_call", { name: patientFirst })}</p>
        </section>
      )}

      <section className="card stack" aria-label={t("cg_alerts")}>
        <div className="card-head" style={{ marginBottom: 0 }}>
          <h2>{t("cg_alerts")}</h2>
          {fresh.length > 0 && <span className="chip crit">{t("cg_new", { n: fresh.length })}</span>}
        </div>
        {data.alerts.length === 0 && <p className="muted small">{t("cg_no_alerts", { name: patientFirst })}</p>}
        {data.alerts.length > 0 && fresh.length === 0 && <p className="muted small">{t("cg_no_new")}</p>}
        {fresh.map((al) => (
          <div key={al.id} className={`callout ${al.urgent ? "crit" : "warn"}`}>
            <Icon name="alert" />
            <div className="grow">
              <p className="strong">{label(al)} · <span className="small" style={{ fontWeight: 500 }}>{when(al.at, tz, lang)}</span></p>
              <p>{al.message}</p>
              <button
                type="button" className="btn sm" style={{ marginTop: 10 }}
                disabled={busy !== null} onClick={() => void markSeen(al.id)}
              >
                <Icon name="check" />{t("cg_mark_seen")}
              </button>
            </div>
          </div>
        ))}
        {fresh.length > 1 && (
          <button type="button" className="btn ghost sm" disabled={busy !== null} onClick={() => void markSeen(null)}>
            {t("cg_mark_all_seen")}
          </button>
        )}
        {seen.length > 0 && (
          <details>
            <summary className="small ink-2" style={{ cursor: "pointer" }}>{t("cg_earlier")} ({seen.length})</summary>
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0, marginTop: 10 }}>
              {seen.map((al) => (
                <li key={al.id} className="small">
                  <span className="strong">{label(al)}</span> <span className="muted">· {when(al.at, tz, lang)}</span>
                  <p className="ink-2">{al.message}</p>
                  {al.seen_at && <p className="tiny muted">{t("cg_seen", { when: when(al.seen_at, tz, lang) })}</p>}
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <section className="card flush">
        <div className="card-head" style={{ padding: "16px 18px 0", marginBottom: 0 }}>
          <h2>{t("cg_todays_meds", { name: patientFirst })}</h2>
        </div>
        {data.today.length === 0 ? (
          <Empty icon="pill">{t("none_today")}</Empty>
        ) : (
          <div style={{ marginTop: 8 }}>
            {data.today.map((s) => (
              <div key={s.dosage_id + s.at} className="dose">
                <div className="time">{timeOf(s.at, tz)}</div>
                <div className="grow">
                  <div className="strong">{s.medicine}</div>
                  <div className="small muted">{s.dose}</div>
                </div>
                <SlotChip state={s.state} />
              </div>
            ))}
          </div>
        )}
        <p className="tiny muted" style={{ padding: "0 18px 14px" }}>
          {data.last_checkin
            ? t("cg_last_checkin", { when: when(data.last_checkin.at, tz, lang) })
            : t("no_checkin_yet")}
        </p>
      </section>

      <section className="card">
        <div className="card-head">
          <h2>{t("this_week")}</h2>
          {anyScheduled && total > 0 && <span className="small ink-2 num">{t("week_summary", { taken: a.taken, total })}</span>}
        </div>
        {anyScheduled ? (
          <>
            <div className="week" role="list">
              {data.week.map((d) => (
                <div key={d.date} role="listitem" className={`d ${isToday(d.date, tz) ? "today" : ""}`}>
                  <span className={`dow ${isToday(d.date, tz) ? "today" : ""}`}>{weekdayOf(d.date, lang)}</span>
                  <DayDot state={d.state} />
                </div>
              ))}
            </div>
            <div style={{ marginTop: 14 }}><WeekLegend /></div>
          </>
        ) : (
          <p className="muted small">{t("week_none")}</p>
        )}
      </section>

      {data.how_doing && (
        <section className="card">
          <div className="card-head">
            <h2>{t("cg_how_doing", { name: patientFirst })}</h2>
            <span className="tiny muted">{dayLabel(data.how_doing.at, tz, lang)}</span>
          </div>
          <p className="ink-2">{data.how_doing.summary}</p>
        </section>
      )}

      <button
        type="button" className="btn ghost sm" style={{ alignSelf: "center" }}
        onClick={() => {
          clearIdentity();
          router.push("/");
        }}
      >
        <Icon name="logout" />{t("switch_user")}
      </button>
    </>
  );
}
