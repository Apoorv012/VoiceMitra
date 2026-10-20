"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { Adherence, EscalationList } from "@/components/staff/parts";
import { AttentionChip, Avatar } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { ago, clockLabel, dayLabel, dayOfDate, isToday, timeOf, weekdayOf, when } from "@/lib/format";
import type { DayView, LogView, MedicineView, PatientClinical, SlotView } from "@/lib/types";

const CELL: Record<string, [string, IconName, string]> = {
  taken: ["good", "check", "Taken"], partial: ["warn", "alert", "Partly taken"], missed: ["crit", "x", "Missed"],
  later: ["warn", "clock", "Said they'd take it later"], unknown: ["", "help", "Patient wasn't sure"],
  skipped: ["", "shield", "Skipped on advice"], upcoming: ["pending", "clock", "Upcoming"],
  due: ["warn", "clock", "Due now"], no_checkin: ["", "help", "No check-in"],
};

const BAND: Record<string, [string, string]> = { ok: ["good", "Fine"], watch: ["warn", "Worth a look"], urgent: ["crit", "Needs attention"] };

function Section({ id, title, children, aside }: { id: string; title: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section id={id} className="stack-sm">
      <div className="row between"><h2>{title}</h2>{aside}</div>
      {children}
    </section>
  );
}

function DoseCell({ s, tz }: { s: SlotView; tz: string }) {
  const [tone, icon, label] = CELL[s.state] ?? CELL.no_checkin;
  return (
    <span className={`cell ${tone}`} title={`${label}${s.note ? ` — ${s.note}` : ""}`} aria-label={`${s.medicine} ${timeOf(s.at, tz)}: ${label}`}>
      <Icon name={icon} />{timeOf(s.at, tz)} {s.medicine}
      {s.state === "missed" && s.note ? <em style={{ fontWeight: 400 }}>· {s.note}</em> : null}
    </span>
  );
}

function AdherenceGrid({ days, tz }: { days: DayView[]; tz: string }) {
  const shown = [...days].reverse().filter((d) => d.slots.length > 0);
  if (shown.length === 0) return <p className="muted">No doses were scheduled in the last two weeks.</p>;
  return (
    <>
      <div className="doses-grid">
        {shown.map((d) => (
          <div key={d.date} style={{ display: "contents" }}>
            <span className="day">{isToday(d.date, tz) ? "Today" : `${weekdayOf(d.date)} ${dayOfDate(d.date)}`}</span>
            <span className="cells">{d.slots.map((s) => <DoseCell key={s.dosage_id + s.at} s={s} tz={tz} />)}</span>
          </div>
        ))}
      </div>
      <div className="legend" style={{ marginTop: 14 }}>
        {(["taken", "partial", "missed", "no_checkin", "upcoming"] as const).map((k) => {
          const [tone, icon, label] = CELL[k];
          return <span key={k}><span className={`cell ${tone}`}><Icon name={icon} /></span>{label}</span>;
        })}
      </div>
    </>
  );
}

function SymptomChart({ logs }: { logs: LogView[] }) {
  const series = [...logs].slice(0, 14).reverse();
  if (series.length < 2) return null;
  return (
    <div className="card">
      <p className="eyebrow" style={{ marginBottom: 10 }}>Seriousness at each check-in (1–10)</p>
      <div className="bars" role="img" aria-label={`Seriousness scores, oldest to newest: ${series.map((l) => l.seriousness).join(", ")}`}>
        {series.map((l, i) => (
          <span
            key={l.id}
            className={`bar ${l.band !== "ok" ? l.band : ""} ${i === series.length - 1 && l.band === "ok" ? "latest" : ""}`}
            style={{ height: `${l.seriousness * 10}%` }}
            title={`${l.seriousness}/10`}
          />
        ))}
      </div>
      <p className="tiny muted" style={{ marginTop: 8 }}>Amber is 5–7 (worth a look), red is 8–10 (needs attention). Latest on the right.</p>
    </div>
  );
}

function AddPrescription({ patientId, onAdded }: { patientId: string; onAdded: () => void }) {
  const today = new Date().toISOString().slice(0, 10);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <details className="disclosure card">
      <summary><Icon name="plus" />Add a prescription</summary>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          setBusy(true);
          setError(null);
          try {
            await api(`/api/patients/${patientId}/prescriptions`, {
              method: "POST",
              json: {
                medicines: [{
                  medicine_name: String(f.get("medicine_name")).trim(),
                  dosage: String(f.get("dosage")).trim(),
                  frequency: f.get("frequency"),
                  times: String(f.get("times") ?? "").split(",").map((t) => t.trim()).filter(Boolean),
                  from_date: f.get("from_date"),
                  to_date: f.get("to_date") || null,
                }],
              },
            });
            (e.target as HTMLFormElement).reset();
            onAdded();
          } catch (err) {
            setError(err instanceof ApiError ? err.message : "Could not add the prescription");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          <div className="field"><label htmlFor="rx-name">Medicine</label><input id="rx-name" name="medicine_name" type="text" required /></div>
          <div className="field"><label htmlFor="rx-dose">Dose</label><input id="rx-dose" name="dosage" type="text" placeholder="1 tablet" required /></div>
          <div className="field">
            <label htmlFor="rx-freq">How often</label>
            <select id="rx-freq" name="frequency" defaultValue="fixed_times">
              <option value="fixed_times">At set times each day</option>
              <option value="daily">Every day</option>
              <option value="weekly">Once a week</option>
              <option value="every_x_day">Every few days</option>
            </select>
          </div>
          <div className="field"><label htmlFor="rx-times">Times</label><input id="rx-times" name="times" type="text" placeholder="09:00, 21:00" /><span className="hint">24-hour, comma separated</span></div>
          <div className="field"><label htmlFor="rx-from">From</label><input id="rx-from" name="from_date" type="date" defaultValue={today} required /></div>
          <div className="field"><label htmlFor="rx-to">Until (optional)</label><input id="rx-to" name="to_date" type="date" /></div>
        </div>
        {error && <p className="callout crit" role="alert">{error}</p>}
        <div><button className="btn" type="submit" disabled={busy}>{busy ? "Adding…" : "Add prescription"}</button></div>
      </form>
    </details>
  );
}

function MedicineCard({ m }: { m: MedicineView }) {
  const freq = m.frequency === "weekly" ? "Once a week" : m.frequency === "daily" ? "Every day" : m.frequency === "every_x_day" ? "Every few days" : "Daily";
  return (
    <div className="card" style={m.active ? undefined : { opacity: 0.65 }}>
      <div className="row between top">
        <div>
          <strong style={{ fontSize: "1.05rem" }}>{m.name}</strong>
          <p className="ink-2 small">{m.dose}</p>
        </div>
        <span className={`chip ${m.active ? "accent" : ""}`}>{m.active ? "Current" : "Finished"}</span>
      </div>
      <p className="small" style={{ marginTop: 10 }}>
        <Icon name="clock" /> {freq}{m.times.length ? ` at ${m.times.map(clockLabel).join(", ")}` : ""}
      </p>
      <p className="small muted" style={{ marginTop: 2 }}>
        From {dayOfDate(m.from_date)}{m.to_date ? ` until ${dayOfDate(m.to_date)}` : ""}
        {m.active && m.days_left !== null ? ` · ${m.days_left} days left` : ""}
      </p>
      {m.active && m.known > 0 && <p className="small" style={{ marginTop: 8 }}>{m.taken} of {m.known} taken this week</p>}
    </div>
  );
}

export function PatientClinicalView({
  data, base, doctorId, onChanged,
}: { data: PatientClinical; base: string; doctorId?: string; onChanged: () => void }) {
  const tz = data.timezone;
  const [allCheckins, setAllCheckins] = useState(false);
  const latest = data.logs[0];
  const checkins = allCheckins ? data.checkins : data.checkins.slice(0, 6);

  return (
    <>
      <Link href={base} className="crumb"><Icon name="chevron-left" />Overview</Link>

      <div className="page-head">
        <div className="row" style={{ gap: 16 }}>
          <Avatar name={data.patient.name} size="lg" tone={data.attention.level === "critical" ? "crit" : data.attention.level === "warning" ? "warn" : ""} />
          <div>
            <h1>{data.patient.name}</h1>
            <p className="ink-2">{data.patient.age} years · {data.phone_number}{data.address ? ` · ${data.address}` : ""}</p>
          </div>
        </div>
        <AttentionChip level={data.attention.level} />
      </div>

      <div className="row wrap top" style={{ gap: 12, alignItems: "stretch" }}>
        <div className={`callout ${data.allergies.length ? "warn" : ""} grow`}>
          <Icon name="shield" />
          <div><p className="strong">Allergies</p><p>{data.allergies.length ? data.allergies.join(", ") : "None known"}</p></div>
        </div>
        {data.attention.reasons.length > 0 && (
          <div className={`callout ${data.attention.level === "critical" ? "crit" : "warn"} grow`} style={{ flexBasis: 320 }}>
            <Icon name="alert" />
            <div><p className="strong">Why this patient is flagged</p><ul className="reasons" style={{ marginTop: 2 }}>{data.attention.reasons.map((r) => <li key={r}>{r}</li>)}</ul></div>
          </div>
        )}
      </div>

      <div className="tiles">
        <div className="tile">
          <span className="label">Adherence, last 7 days</span>
          <span className="value">{data.adherence.rate === null ? "—" : <>{data.adherence.rate}<small>%</small></>}</span>
          <span className="sub">{data.adherence.rate === null ? "No doses heard about yet" : `${data.adherence.taken} of ${data.adherence.taken + data.adherence.missed} doses taken`}</span>
        </div>
        <div className="tile">
          <span className="label">Latest symptom score</span>
          <span className="value">{latest ? <>{latest.seriousness}<small>/10</small></> : "—"}</span>
          <span className="sub">{latest ? <span className={`chip ${BAND[latest.band][0]}`}>{BAND[latest.band][1]}</span> : "None reported"}{latest ? ` ${ago(latest.at)}` : ""}</span>
        </div>
        <div className="tile">
          <span className="label">Last check-in</span>
          <span className="value" style={{ fontSize: "1.3rem" }}>{data.checkins[0] ? ago(data.checkins[0].at) : "—"}</span>
          <span className="sub">{data.checkins[0] ? when(data.checkins[0].at, tz) : "No calls yet"}</span>
        </div>
        <div className="tile">
          <span className="label">Family contact</span>
          <span className="value" style={{ fontSize: "1.3rem" }}>{data.caregiver ? data.caregiver.name : "—"}</span>
          <span className="sub">{data.caregiver ? `${data.caregiver.relation} · ${data.caregiver.phone_number}` : "None on file"}</span>
        </div>
      </div>

      <nav className="subnav" aria-label="Sections">
        <a href="#adherence">Adherence</a><a href="#symptoms">Symptoms</a><a href="#medicines">Medicines</a><a href="#calls">Calls</a>
      </nav>

      <Section id="adherence" title="Doses, last 14 days" aside={<Adherence a={data.adherence} compact />}>
        <div className="card"><AdherenceGrid days={data.days} tz={tz} /></div>
      </Section>

      <Section id="symptoms" title="Symptoms reported">
        {data.logs.length === 0 ? <div className="card"><p className="muted">Nothing has been reported yet.</p></div> : (
          <>
            <SymptomChart logs={data.logs} />
            <ul className="timeline">
              {data.logs.slice(0, 8).map((l) => (
                <li key={l.id} className={l.band === "urgent" ? "crit" : l.band === "watch" ? "warn" : "good"}>
                  <p className="when">{dayLabel(l.at, tz)}, {timeOf(l.at, tz)}</p>
                  <div className="card" style={{ marginTop: 8 }}>
                    <div className="row between top">
                      <span className={`chip ${BAND[l.band][0]}`}>{l.seriousness}/10 · {BAND[l.band][1]}</span>
                      <Link href={`/calls/${l.call_id}`} className="btn ghost sm">Transcript</Link>
                    </div>
                    <p style={{ marginTop: 10 }}>{l.summary}</p>
                    {l.symptoms.length > 0 && (
                      <div className="row wrap" style={{ gap: 6, marginTop: 10 }}>
                        {l.symptoms.map((s) => (
                          <span key={s.name + (s.location ?? "")} className={`chip ${s.severity === "severe" ? "crit" : s.severity === "moderate" ? "warn" : ""}`}>
                            {s.name}{s.location ? ` (${s.location})` : ""} · {s.severity}{s.duration_note ? ` · ${s.duration_note}` : ""}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Section>

      <Section id="medicines" title="Prescriptions">
        <div className="tiles" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          {data.medicines.length === 0 ? <div className="card"><p className="muted">No medicines yet.</p></div> : data.medicines.map((m) => <MedicineCard key={m.dosage_id} m={m} />)}
        </div>
        <AddPrescription patientId={data.patient.id} onAdded={onChanged} />
      </Section>

      <Section id="calls" title="Calls and escalations">
        {data.escalations.length > 0 && <div className="card flush"><EscalationList rows={data.escalations} doctorId={doctorId} showPatient={false} /></div>}
        <div className="card flush">
          {data.checkins.length === 0 ? <p className="empty">No check-in calls yet.</p> : (
            <ul className="list">
              {checkins.map((c) => (
                <li key={c.call_id}>
                  <div className="grow">
                    <strong>{when(c.at, tz)}</strong>
                    <span className="small muted"> · {c.type.replace(/_/g, " ")}</span>
                    <div className="row wrap" style={{ gap: 6, marginTop: 6 }}>
                      {c.medicine_status && <span className={`chip ${c.medicine_status === "taken" ? "good" : c.medicine_status === "not_taken" ? "crit" : ""}`}>Medicine: {c.medicine_status.replace(/_/g, " ")}</span>}
                      {c.escalated && <span className="chip crit"><Icon name="stethoscope" />{c.doctor_connected ? "Doctor connected" : "Escalated"}</span>}
                      {c.symptoms.map((s) => <span key={s} className="chip">{s}</span>)}
                    </div>
                  </div>
                  <Link href={`/calls/${c.call_id}`} className="btn ghost sm">Transcript</Link>
                </li>
              ))}
            </ul>
          )}
          {data.checkins.length > 6 && (
            <div style={{ padding: 12, textAlign: "center", borderTop: "1px solid var(--line)" }}>
              <button type="button" className="btn ghost sm" onClick={() => setAllCheckins((v) => !v)}>{allCheckins ? "Show fewer" : `Show all ${data.checkins.length}`}</button>
            </div>
          )}
        </div>
        {data.alerts.length > 0 && (
          <div className="card">
            <p className="eyebrow" style={{ marginBottom: 8 }}>Alerts sent to the family</p>
            <ul className="stack-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {data.alerts.slice(0, 5).map((a) => (
                <li key={a.call_id + a.at} className="small"><span className="muted">{ago(a.at)}{a.caregiver ? ` · to ${a.caregiver}` : ""}:</span> {a.message}</li>
              ))}
            </ul>
          </div>
        )}
      </Section>
    </>
  );
}
