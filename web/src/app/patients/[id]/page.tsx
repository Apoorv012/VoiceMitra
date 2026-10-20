"use client";

import { useParams } from "next/navigation";
import { useEffect } from "react";
import { useCall } from "@/components/call/CallProvider";
import { Icon } from "@/components/Icon";
import { DayDot, Empty, ErrorState, Loading, SlotChip, WeekLegend } from "@/components/ui";
import { useApi } from "@/lib/api";
import { dayLabel, fullDateToday, greetingKey, inWords, isToday, timeOf, weekdayOf, when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { PatientHome } from "@/lib/types";

export default function Today() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientHome>(`/api/app/patients/${id}/home`, 30_000);
  const { t, lang } = useT();
  const call = useCall();

  // A finished call has just logged doses and symptoms: show them without waiting for the next refresh.
  useEffect(() => {
    if (call.phase === "ended") void mutate();
  }, [call.phase, mutate]);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const tz = data.timezone;
  const first = data.patient.name.split(" ")[0];
  const a = data.adherence;
  const total = a.taken + a.missed + a.unrecorded;
  const anyScheduled = data.week.some((d) => d.state !== "none");

  return (
    <>
      <section className="hello">
        <p className="eyebrow">{t(greetingKey(tz))} · {fullDateToday(tz, lang)}</p>
        <h1>{t("namaste", { name: first })}</h1>
      </section>

      <section className="card talk">
        <span className={call.inCall ? "pulse" : ""}>
          <span className="mic"><Icon name="mic" /></span>
        </span>
        <div>
          <h2>{t("talk_title")}</h2>
          <p className="ink-2 small" style={{ marginTop: 4 }}>{t("talk_sub")}</p>
        </div>
        {call.inCall ? (
          <button type="button" className="btn good xl block" onClick={call.reopen}>
            <Icon name="phone" />{t("talk_in_call")}
          </button>
        ) : (
          <button type="button" className="btn xl block" onClick={() => void call.start()} disabled={call.phase === "starting"}>
            <Icon name="phone" />{call.phase === "starting" ? t("talk_starting") : t("talk_btn")}
          </button>
        )}
        <p className="tiny muted">
          {data.last_checkin
            ? t("last_checkin", { when: when(data.last_checkin.at, tz, lang) })
            : t("no_checkin_yet")}
        </p>
      </section>

      {data.next_dose && (
        <section className="callout accent" aria-label={t("next_dose")}>
          <Icon name="pill" className="lg" />
          <div>
            <p className="eyebrow" style={{ color: "inherit", opacity: 0.8 }}>{t("next_dose")}</p>
            <p className="strong" style={{ fontSize: "1.1rem" }}>
              {data.next_dose.medicine} <span className="small" style={{ fontWeight: 500 }}>· {data.next_dose.dose}</span>
            </p>
            <p className="small">
              {dayLabel(data.next_dose.at, tz, lang)}, {timeOf(data.next_dose.at, tz)}
              {data.next_dose.state !== "due" && <> · {inWords(data.next_dose.at, lang)}</>}
            </p>
          </div>
        </section>
      )}

      <section className="card flush">
        <div className="card-head" style={{ padding: "16px 18px 0", marginBottom: 0 }}>
          <h2>{t("todays_meds")}</h2>
        </div>
        {data.today.length === 0 ? (
          <Empty icon="pill">{t("none_today")}</Empty>
        ) : (
          <div style={{ marginTop: 8 }}>
            {data.today.map((s) => (
              <div key={s.dosage_id + s.at} className={`dose ${data.next_dose && data.next_dose.dosage_id === s.dosage_id && data.next_dose.at === s.at ? "next" : ""}`}>
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
            {a.unrecorded > 0 && <p className="tiny muted" style={{ marginTop: 10 }}>{t("week_unchecked", { n: a.unrecorded })}</p>}
          </>
        ) : (
          <p className="muted small">{t("week_none")}</p>
        )}
      </section>

      {data.how_doing && (
        <section className="card">
          <div className="card-head">
            <h2>{t("how_doing")}</h2>
            <span className="tiny muted">{dayLabel(data.how_doing.at, tz, lang)}</span>
          </div>
          <p style={{ marginBottom: 10 }}>
            <span className={`chip lg ${data.how_doing.band === "ok" ? "good" : data.how_doing.band === "watch" ? "warn" : "crit"}`}>
              <Icon name={data.how_doing.band === "ok" ? "check" : "alert"} />
              {t(data.how_doing.band === "ok" ? "doing_ok" : data.how_doing.band === "watch" ? "doing_watch" : "doing_urgent")}
            </span>
          </p>
          <p className="ink-2">{data.how_doing.summary}</p>
        </section>
      )}

      {data.reminders.length > 0 && (
        <section className="callout">
          <Icon name="clock" />
          <div>
            {data.reminders.map((r) => (
              <p key={r}>{t("reminder_at", { time: `${dayLabel(r, tz, lang)}, ${timeOf(r, tz)}` })}</p>
            ))}
          </div>
        </section>
      )}

      {data.caregiver && (
        <p className="small muted" style={{ textAlign: "center", padding: "4px 12px" }}>
          <Icon name="heart" /> {t("caregiver_line", { name: data.caregiver.name, relation: data.caregiver.relation })}
        </p>
      )}
    </>
  );
}
