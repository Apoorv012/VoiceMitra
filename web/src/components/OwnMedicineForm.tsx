"use client";

// Add or change one of the patient's own medicines (the kind they add themselves; the doctor's prescription is
// entered by staff and can't be changed here). Big fields, one time picker per dose, Hindi/English.

import { useId, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { useT, type MessageKey } from "@/lib/i18n";
import type { MedicineView } from "@/lib/types";

type Often = "fixed_times" | "weekly" | "every_x_day";
const MAX_TIMES = 6;

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function OwnMedicineForm({
  patientId, editing, onDone, onCancel,
}: {
  patientId: string;
  editing?: MedicineView;            // absent = adding a new one
  onDone: (name: string) => void;
  onCancel: () => void;
}) {
  const { t } = useT();
  const ids = useId();
  const [name, setName] = useState(editing?.name ?? "");
  const [dose, setDose] = useState(editing?.dose ?? "");
  const [times, setTimes] = useState<string[]>(editing?.times.length ? editing.times : ["08:00"]);
  const [often, setOften] = useState<Often>(
    editing?.frequency === "weekly" ? "weekly" : editing?.frequency === "every_x_day" ? "every_x_day" : "fixed_times");
  const [every, setEvery] = useState(editing?.interval_days ?? 2);
  const [from, setFrom] = useState(editing?.from_date ?? todayISO());
  const [until, setUntil] = useState(editing?.to_date ?? "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<MessageKey | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    const cleanTimes = [...new Set(times.filter(Boolean))].sort();
    if (!name.trim()) return setProblem("f_need_name");
    if (!dose.trim()) return setProblem("f_need_dose");
    if (cleanTimes.length === 0) return setProblem("f_need_time");
    if (until && until < from) return setProblem("f_bad_dates");
    setBusy(true);
    setProblem(null);
    const json = {
      medicine_name: name.trim(), dosage: dose.trim(), frequency: often, times: cleanTimes,
      interval_days: often === "every_x_day" ? every : null, from_date: from, to_date: until || null,
    };
    try {
      if (editing) await api(`/api/patients/${patientId}/medicines/${editing.dosage_id}`, { method: "PUT", json });
      else await api(`/api/patients/${patientId}/own-medicines`, { method: "POST", json });
      onDone(name.trim());
    } catch {
      setProblem("f_save_error");  // the checks above match the server's, so this is a network/server problem
    } finally {
      setBusy(false);
    }
  }

  const choices: [Often, MessageKey][] = [["fixed_times", "f_every_day"], ["weekly", "f_once_week"], ["every_x_day", "f_every_few"]];

  return (
    <form className="card stack" onSubmit={(e) => void save(e)} noValidate aria-labelledby={`${ids}-title`}>
      <h2 id={`${ids}-title`}>{editing ? t("f_edit_title", { name: editing.name }) : t("f_add_title")}</h2>

      <div className="field">
        <label htmlFor={`${ids}-name`}>{t("f_name")}</label>
        <input id={`${ids}-name`} type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={80}
               autoComplete="off" required />
      </div>
      <div className="field">
        <label htmlFor={`${ids}-dose`}>{t("f_dose")}</label>
        <input id={`${ids}-dose`} type="text" value={dose} onChange={(e) => setDose(e.target.value)} maxLength={80}
               placeholder={t("f_dose_ph")} autoComplete="off" required />
      </div>

      <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="strong small ink-2" style={{ marginBottom: 6 }}>{t("f_times")}</legend>
        <div className="stack-sm">
          {times.map((tm, i) => (
            <div key={i} className="row" style={{ gap: 8 }}>
              <input type="time" value={tm} aria-label={`${t("f_times")} ${i + 1}`} style={{ flex: 1 }}
                     onChange={(e) => setTimes(times.map((x, j) => (j === i ? e.target.value : x)))} />
              {times.length > 1 && (
                <button type="button" className="btn ghost sm" aria-label={t("f_remove_time")}
                        onClick={() => setTimes(times.filter((_, j) => j !== i))}><Icon name="x" /></button>
              )}
            </div>
          ))}
        </div>
        {times.length < MAX_TIMES && (
          <div>
            <button type="button" className="btn secondary sm" style={{ marginTop: 8 }}
                    onClick={() => setTimes([...times, ""])}><Icon name="plus" />{t("f_add_time")}</button>
          </div>
        )}
      </fieldset>

      <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
        <legend className="strong small ink-2" style={{ marginBottom: 6 }}>{t("f_how_often")}</legend>
        <div className="stack-sm">
          {choices.map(([v, label]) => (
            <label key={v} className="row" style={{ gap: 10, fontWeight: 500, minHeight: 40 }}>
              <input type="radio" name={`${ids}-often`} value={v} checked={often === v} onChange={() => setOften(v)}
                     style={{ width: 20, height: 20 }} />
              {t(label)}
            </label>
          ))}
        </div>
        {often === "weekly" && <span className="hint">{t("f_week_hint")}</span>}
        {often === "every_x_day" && (
          <div className="field" style={{ marginTop: 8 }}>
            <label htmlFor={`${ids}-every`}>{t("f_every_n")}</label>
            <input id={`${ids}-every`} type="number" min={2} max={90} inputMode="numeric" value={every}
                   onChange={(e) => setEvery(Math.max(2, Math.min(90, Number(e.target.value) || 2)))} style={{ maxWidth: 120 }} />
          </div>
        )}
      </fieldset>

      <div className="form-grid">
        <div className="field">
          <label htmlFor={`${ids}-from`}>{t("f_from")}</label>
          <input id={`${ids}-from`} type="date" value={from} onChange={(e) => setFrom(e.target.value || todayISO())} required />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-until`}>{t("f_until")}</label>
          <input id={`${ids}-until`} type="date" value={until} min={from} onChange={(e) => setUntil(e.target.value)} />
        </div>
      </div>

      {problem && <div className="callout crit" role="alert"><Icon name="alert" /><p>{t(problem)}</p></div>}

      <div className="row" style={{ gap: 8 }}>
        <button type="submit" className="btn" disabled={busy}>{t("f_save")}</button>
        <button type="button" className="btn secondary" disabled={busy} onClick={onCancel}>{t("f_cancel")}</button>
      </div>
    </form>
  );
}
