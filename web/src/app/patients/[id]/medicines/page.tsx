"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { OwnMedicineForm } from "@/components/OwnMedicineForm";
import { Empty, ErrorState, Loading } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { clockLabel, dayOfDate } from "@/lib/format";
import { useT, type MessageKey } from "@/lib/i18n";
import type { MedicineView, PatientMedicines } from "@/lib/types";

// Two kinds (backend/routers/medicines.py): the doctor's prescription, which staff enter and the patient can't
// change, and the patient's own medicines, which they add, change and remove here.

function Schedule({ m }: { m: MedicineView }) {
  const { t } = useT();
  const every = m.frequency === "every_x_day" && m.interval_days;
  const key: MessageKey = every ? "med_every" : m.frequency === "weekly" ? "med_weekly" : m.frequency === "fixed_times" ? "med_fixed" : "med_daily";
  const times = m.times.length ? m.times.map(clockLabel).join(` ${t("and")} `) : "—";
  return <>{t(key, { times, n: every || 0 })}</>;
}

function Medicine({ m, actions }: { m: MedicineView; actions?: React.ReactNode }) {
  const { t, lang } = useT();
  const pct = m.known ? Math.round((100 * m.taken) / m.known) : null;
  return (
    <article className="card" style={m.active ? undefined : { opacity: 0.7 }}>
      <div className="row top">
        <span className="ico-pill avatar"><Icon name="pill" /></span>
        <div className="grow">
          <h2>{m.name}</h2>
          <p className="ink-2">{m.dose}</p>
        </div>
        {!m.active && m.source === "own" && <span className="chip">{t("med_own_tag")}</span>}
      </div>
      <p className="small" style={{ marginTop: 12 }}><Icon name="clock" /> <Schedule m={m} /></p>
      <p className="small muted" style={{ marginTop: 4 }}>
        {m.to_date ? t("med_until", { date: dayOfDate(m.to_date, lang) }) : ""}
        {m.active && m.days_left !== null && (
          <> · <strong className="ink-2">{m.days_left === 0 ? t("med_last_day") : t("med_days_left", { n: m.days_left })}</strong></>
        )}
      </p>
      {m.active && m.known > 0 && pct !== null && (
        <div style={{ marginTop: 14 }}>
          <div className={`meter ${pct >= 80 ? "good" : pct >= 50 ? "warn" : "crit"}`} role="img" aria-label={`${pct}%`}>
            <span style={{ width: `${pct}%` }} />
          </div>
          <p className="tiny muted" style={{ marginTop: 6 }}>{t("med_week", { taken: m.taken, known: m.known })}</p>
        </div>
      )}
      {actions}
    </article>
  );
}

function OwnActions({ m, patientId, onEdit, onRemoved }: {
  m: MedicineView; patientId: string; onEdit: () => void; onRemoved: (outcome: string) => void;
}) {
  const { t } = useT();
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  async function remove() {
    setBusy(true);
    setFailed(false);
    try {
      const res = await api<{ outcome: string }>(`/api/patients/${patientId}/medicines/${m.dosage_id}`, { method: "DELETE" });
      onRemoved(res.outcome);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 14, borderTop: "1px solid var(--line)", paddingTop: 12 }}>
      {asking ? (
        <div className="stack-sm">
          <p className="strong">{t("med_remove_q", { name: m.name })}</p>
          {failed && <p className="small" role="alert" style={{ color: "var(--crit-ink)" }}>{t("med_remove_error")}</p>}
          <div className="row wrap" style={{ gap: 8 }}>
            <button type="button" className="btn danger sm" disabled={busy} onClick={() => void remove()}>{t("med_remove_yes")}</button>
            <button type="button" className="btn secondary sm" disabled={busy} onClick={() => setAsking(false)}>{t("med_keep")}</button>
          </div>
        </div>
      ) : (
        <div className="row wrap" style={{ gap: 8 }}>
          <button type="button" className="btn secondary sm" onClick={onEdit}><Icon name="pencil" />{t("med_edit")}</button>
          <button type="button" className="btn ghost sm" onClick={() => setAsking(true)}><Icon name="trash" />{t("med_remove")}</button>
        </div>
      )}
    </div>
  );
}

export default function Medicines() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientMedicines>(`/api/app/patients/${id}/medicines`, 60_000);
  const { t } = useT();
  const [form, setForm] = useState<"new" | MedicineView | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const prescribed = data.medicines.filter((m) => m.active && m.source !== "own");
  const own = data.medicines.filter((m) => m.active && m.source === "own");
  const past = data.medicines.filter((m) => !m.active);

  function done(message: string) {
    setForm(null);
    setNotice(message);
    void mutate();
  }

  // One of the patient's own: its card with Change / Remove, or the form while it is being changed.
  function ownCard(m: MedicineView) {
    if (form !== null && form !== "new" && form.dosage_id === m.dosage_id) {
      return <OwnMedicineForm key={m.dosage_id} patientId={id} editing={m} onCancel={() => setForm(null)}
                              onDone={(name) => done(t("med_saved", { name }))} />;
    }
    return (
      <Medicine key={m.dosage_id} m={m} actions={
        <OwnActions m={m} patientId={id} onEdit={() => { setNotice(null); setForm(m); }}
                    onRemoved={(outcome) => done(t(outcome === "stopped" ? "med_stopped" : "med_deleted", { name: m.name }))} />
      } />
    );
  }

  return (
    <>
      <h1>{t("meds_title")}</h1>

      <div className={`callout ${data.allergies.length ? "warn" : ""}`}>
        <Icon name="shield" />
        <div>
          <p className="strong">{t("allergies")}</p>
          <p>{data.allergies.length ? data.allergies.join(", ") : t("no_allergies")}</p>
        </div>
      </div>

      {notice && (
        <div className="callout good" role="status">
          <Icon name="check" /><p className="grow">{notice}</p>
          <button type="button" className="btn ghost sm" aria-label={t("f_cancel")} onClick={() => setNotice(null)}><Icon name="x" /></button>
        </div>
      )}

      <section className="stack-sm" aria-labelledby="meds-doctor">
        <p className="eyebrow" id="meds-doctor">{t("med_from_doctor")}</p>
        <p className="small ink-2">{t("med_from_doctor_sub")}</p>
        {prescribed.length === 0
          ? <div className="card"><Empty icon="pill">{t("med_doctor_none")}</Empty></div>
          : prescribed.map((m) => <Medicine key={m.dosage_id} m={m} />)}
      </section>

      <section className="stack-sm" aria-labelledby="meds-own">
        <p className="eyebrow" id="meds-own">{t("med_own")}</p>
        <p className="small ink-2">{t("med_own_sub")}</p>
        {own.map(ownCard)}
        {own.length === 0 && form !== "new" && <p className="small muted">{t("med_own_none")}</p>}
        {form === "new" ? (
          <OwnMedicineForm patientId={id} onCancel={() => setForm(null)} onDone={(name) => done(t("med_saved", { name }))} />
        ) : (
          <div>
            <button type="button" className="btn" onClick={() => { setNotice(null); setForm("new"); }}>
              <Icon name="plus" />{t("med_add")}
            </button>
          </div>
        )}
      </section>

      {past.length > 0 && (
        <section className="stack-sm">
          <p className="eyebrow">{t("med_past")}</p>
          {past.map((m) => (m.source === "own" ? ownCard(m) : <Medicine key={m.dosage_id} m={m} />))}
        </section>
      )}
    </>
  );
}
