"use client";

// Staff: add the doctor's prescription -- typed in, or read from a photo into the same rows for checking first
// (nothing is saved until "Save prescription"; the photo isn't kept). Also used to change one medicine.

import { useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { api, ApiError } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import type { MedicineView } from "@/lib/types";

type Draft = components["schemas"]["PrescriptionDraft"];
type Often = "fixed_times" | "daily" | "weekly" | "every_x_day";

type Row = {
  key: number;
  medicine_name: string;
  dosage: string;
  frequency: Often;
  interval_days: number;
  times: string;          // "08:00, 21:00"
  from_date: string;
  to_date: string;
  unsure?: string | null; // from the photo reader
};

const TIME = /^([01]?\d|2[0-3]):([0-5]\d)$/;
const MAX_SIDE = 1600;

let nextKey = 1;
function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function addDays(iso: string, n: number) {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}
function emptyRow(): Row {
  return { key: nextKey++, medicine_name: "", dosage: "", frequency: "fixed_times", interval_days: 2, times: "", from_date: todayISO(), to_date: "" };
}
function rowFromMedicine(m: MedicineView): Row {
  return {
    key: nextKey++, medicine_name: m.name, dosage: m.dose, frequency: m.frequency as Often, interval_days: m.interval_days ?? 2,
    times: m.times.join(", "), from_date: m.from_date, to_date: m.to_date ?? "",
  };
}

function parseTimes(text: string): string[] | null {
  const parts = text.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
  return parts.every((p) => TIME.test(p)) ? parts : null;
}

function toBody(r: Row) {
  return {
    medicine_name: r.medicine_name.trim(), dosage: r.dosage.trim(), frequency: r.frequency,
    interval_days: r.frequency === "every_x_day" ? r.interval_days : null,
    times: parseTimes(r.times) ?? [], from_date: r.from_date, to_date: r.to_date || null,
  };
}

function problemWith(r: Row, n: number): string | null {
  const which = `Medicine ${n}`;
  if (!r.medicine_name.trim()) return `${which}: the name is missing.`;
  if (!r.dosage.trim()) return `${which} (${r.medicine_name}): the dose is missing.`;
  if (parseTimes(r.times) === null) return `${which} (${r.medicine_name}): times must look like 08:00, 21:00.`;
  if (r.to_date && r.to_date < r.from_date) return `${which} (${r.medicine_name}): it ends before it starts.`;
  return null;
}

/** Shrink a phone photo before upload (also turns it into a JPEG). */
async function shrink(file: File): Promise<{ base64: string; mime: string }> {
  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise<Blob>((ok, fail) => canvas.toBlob((b) => (b ? ok(b) : fail(new Error("encode"))), "image/jpeg", 0.85));
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return { base64: btoa(bin), mime: "image/jpeg" };
}

function RowEditor({ r, n, onChange, onRemove }: { r: Row; n: number; onChange: (r: Row) => void; onRemove?: () => void }) {
  const id = `rx-${r.key}`;
  const set = (patch: Partial<Row>) => onChange({ ...r, ...patch });
  return (
    <fieldset className="card" style={{ margin: 0, background: "var(--sunken)" }}>
      <div className="row between" style={{ marginBottom: 10 }}>
        <legend className="strong" style={{ padding: 0 }}>Medicine {n}</legend>
        {onRemove && <button type="button" className="btn ghost sm" onClick={onRemove}><Icon name="trash" />Remove row</button>}
      </div>
      {r.unsure && <p className="callout warn small" style={{ marginBottom: 10 }}><Icon name="help" />Check: {r.unsure}</p>}
      <div className="form-grid">
        <div className="field"><label htmlFor={`${id}-name`}>Medicine</label>
          <input id={`${id}-name`} type="text" value={r.medicine_name} maxLength={80} onChange={(e) => set({ medicine_name: e.target.value })} /></div>
        <div className="field"><label htmlFor={`${id}-dose`}>Dose</label>
          <input id={`${id}-dose`} type="text" value={r.dosage} maxLength={80} placeholder="1 tablet after food" onChange={(e) => set({ dosage: e.target.value })} /></div>
        <div className="field"><label htmlFor={`${id}-freq`}>How often</label>
          <select id={`${id}-freq`} value={r.frequency} onChange={(e) => set({ frequency: e.target.value as Often })}>
            <option value="fixed_times">Every day, at set times</option>
            {r.frequency === "daily" && <option value="daily">Every day</option>}
            <option value="weekly">Once a week</option>
            <option value="every_x_day">Every few days</option>
          </select></div>
        {r.frequency === "every_x_day" && (
          <div className="field"><label htmlFor={`${id}-every`}>Every how many days</label>
            <input id={`${id}-every`} type="number" min={2} max={90} inputMode="numeric" value={r.interval_days}
                   onChange={(e) => set({ interval_days: Math.max(2, Math.min(90, Number(e.target.value) || 2)) })} /></div>
        )}
        <div className="field"><label htmlFor={`${id}-times`}>Times</label>
          <input id={`${id}-times`} type="text" value={r.times} placeholder="08:00, 21:00" onChange={(e) => set({ times: e.target.value })} />
          <span className="hint">24-hour, comma separated. The reminder call comes at these times.</span></div>
        <div className="field"><label htmlFor={`${id}-from`}>From</label>
          <input id={`${id}-from`} type="date" value={r.from_date} onChange={(e) => set({ from_date: e.target.value || todayISO() })} /></div>
        <div className="field"><label htmlFor={`${id}-to`}>Until (optional)</label>
          <input id={`${id}-to`} type="date" value={r.to_date} min={r.from_date} onChange={(e) => set({ to_date: e.target.value })} /></div>
      </div>
    </fieldset>
  );
}

/** Add a prescription (one or more medicines), by hand or from a photo. */
export function AddPrescription({ patientId, onAdded }: { patientId: string; onAdded: () => void }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Row[]>(() => [emptyRow()]);
  const [busy, setBusy] = useState<"reading" | "saving" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);  // object URL, to compare against while checking
  const fileRef = useRef<HTMLInputElement>(null);

  function reset() {
    if (photo) URL.revokeObjectURL(photo);
    setRows([emptyRow()]); setError(null); setNotes(null); setPhoto(null); setOpen(false);
  }

  async function readPhoto(file: File) {
    setBusy("reading");
    setError(null);
    setNotes(null);
    try {
      let img;
      try { img = await shrink(file); } catch { throw new Error("That file couldn't be opened as a photo. Use a JPEG or PNG."); }
      if (photo) URL.revokeObjectURL(photo);
      setPhoto(URL.createObjectURL(file));
      const draft = await api<Draft>(`/api/patients/${patientId}/prescriptions/read-photo`, {
        method: "POST", json: { image_base64: img.base64, mime_type: img.mime },
      });
      const from = draft.prescribed_on && draft.prescribed_on <= todayISO() ? draft.prescribed_on : todayISO();
      const read: Row[] = draft.medicines.map((m) => ({
        key: nextKey++, medicine_name: m.medicine_name, dosage: m.dosage ?? "",
        frequency: (m.frequency === "daily" ? "fixed_times" : m.frequency) as Often,
        interval_days: m.interval_days ?? 2, times: (m.times ?? []).join(", "),
        from_date: from, to_date: m.days ? addDays(from, m.days - 1) : "", unsure: m.unsure,
      }));
      const kept = rows.filter((r) => r.medicine_name.trim());
      setRows(read.length || kept.length ? [...kept, ...read] : [emptyRow()]);
      const dated = draft.prescribed_on ? `Prescription dated ${draft.prescribed_on}. ` : "";
      setNotes(read.length
        ? `${dated}Read ${read.length} medicine${read.length > 1 ? "s" : ""} from the photo. Check every row against the photo before saving.${draft.notes ? ` Note: ${draft.notes}` : ""}`
        : `No medicines could be read from the photo.${draft.notes ? ` ${draft.notes}` : ""} Try a clearer photo, or type them in.`);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Couldn't read the photo");
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function save() {
    const problem = rows.map((r, i) => problemWith(r, i + 1)).find(Boolean);
    if (problem) return setError(problem);
    setBusy("saving");
    setError(null);
    try {
      await api(`/api/patients/${patientId}/prescriptions`, { method: "POST", json: { medicines: rows.map(toBody) } });
      reset();
      onAdded();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn't save: ${err.message}` : "Couldn't save the prescription");
    } finally {
      setBusy(null);
    }
  }

  if (!open) {
    return (
      <div className="row wrap" style={{ gap: 8 }}>
        <button type="button" className="btn" onClick={() => setOpen(true)}><Icon name="plus" />Add a prescription</button>
      </div>
    );
  }

  return (
    <section className="card stack" aria-labelledby="rx-add-title">
      <div className="row between wrap">
        <h3 id="rx-add-title">Add the doctor&rsquo;s prescription</h3>
        <span className="small muted">The patient sees these but can&rsquo;t change them.</span>
      </div>

      <div className="row wrap" style={{ gap: 10 }}>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/*" hidden
               onChange={(e) => { const f = e.target.files?.[0]; if (f) void readPhoto(f); }} />
        <button type="button" className="btn secondary" disabled={busy !== null} onClick={() => fileRef.current?.click()}>
          <Icon name="camera" />{busy === "reading" ? "Reading the photo…" : photo ? "Read another photo" : "Upload a photo of the prescription"}
        </button>
        <span className="small muted">or type the medicines below. A photo only fills in the rows; nothing is saved until you save.</span>
      </div>

      {notes && <p className="callout accent small" role="status"><Icon name="file" />{notes}</p>}

      <div className={photo ? "two-col" : undefined} style={photo ? { alignItems: "start" } : undefined}>
        {photo && (
          // eslint-disable-next-line @next/next/no-img-element -- a local object URL, not something to optimise
          <img src={photo} alt="The uploaded prescription" style={{ width: "100%", borderRadius: 10, border: "1px solid var(--line)", position: "sticky", top: 80 }} />
        )}
        <div className="stack-sm">
          {rows.map((r, i) => (
            <RowEditor key={r.key} r={r} n={i + 1}
                       onChange={(nr) => setRows(rows.map((x) => (x.key === r.key ? { ...nr, unsure: x.unsure } : x)))}
                       onRemove={rows.length > 1 ? () => setRows(rows.filter((x) => x.key !== r.key)) : undefined} />
          ))}
          <div>
            <button type="button" className="btn ghost sm" onClick={() => setRows([...rows, emptyRow()])}><Icon name="plus" />Another medicine</button>
          </div>
        </div>
      </div>

      {error && <p className="callout crit" role="alert"><Icon name="alert" />{error}</p>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="btn" disabled={busy !== null} onClick={() => void save()}>
          {busy === "saving" ? "Saving…" : `Save prescription (${rows.length} medicine${rows.length > 1 ? "s" : ""})`}
        </button>
        <button type="button" className="btn secondary" disabled={busy !== null} onClick={reset}>Cancel</button>
      </div>
    </section>
  );
}

/** Change one medicine (staff may change either kind). */
export function EditMedicine({ patientId, m, onDone, onCancel }: { patientId: string; m: MedicineView; onDone: () => void; onCancel: () => void }) {
  const [row, setRow] = useState<Row>(() => rowFromMedicine(m));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save() {
    const problem = problemWith(row, 1);
    if (problem) return setError(problem.replace(/^Medicine 1( \([^)]*\))?: /, ""));
    if (m.source === "own" && !(parseTimes(row.times) ?? []).length) return setError("The patient's own medicines need at least one time.");
    setBusy(true);
    setError(null);
    try {
      await api(`/api/patients/${patientId}/medicines/${m.dosage_id}`, { method: "PUT", json: toBody(row) });
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn't save: ${err.message}` : "Couldn't save");
      setBusy(false);
    }
  }

  return (
    <div className="stack-sm">
      <RowEditor r={row} n={1} onChange={setRow} />
      {error && <p className="callout crit" role="alert"><Icon name="alert" />{error}</p>}
      <div className="row" style={{ gap: 8 }}>
        <button type="button" className="btn sm" disabled={busy} onClick={() => void save()}>{busy ? "Saving…" : "Save"}</button>
        <button type="button" className="btn secondary sm" disabled={busy} onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}
