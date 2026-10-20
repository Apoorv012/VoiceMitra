"use client";

import { useParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Empty, ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { clockLabel, dayOfDate } from "@/lib/format";
import { useT, type MessageKey } from "@/lib/i18n";
import type { MedicineView, PatientMedicines } from "@/lib/types";

function Schedule({ m }: { m: MedicineView }) {
  const { t } = useT();
  const key: MessageKey = m.frequency === "weekly" ? "med_weekly" : m.frequency === "fixed_times" ? "med_fixed" : "med_daily";
  const times = m.times.length ? m.times.map(clockLabel).join(` ${t("and")} `) : "—";
  return <>{t(key, { times })}</>;
}

function Medicine({ m }: { m: MedicineView }) {
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
    </article>
  );
}

export default function Medicines() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientMedicines>(`/api/app/patients/${id}/medicines`, 60_000);
  const { t } = useT();

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const current = data.medicines.filter((m) => m.active);
  const past = data.medicines.filter((m) => !m.active);

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

      {data.medicines.length === 0 && <div className="card"><Empty icon="pill">{t("no_meds")}</Empty></div>}

      {current.length > 0 && (
        <section className="stack-sm">
          <p className="eyebrow">{t("med_current")}</p>
          {current.map((m) => <Medicine key={m.dosage_id} m={m} />)}
        </section>
      )}
      {past.length > 0 && (
        <section className="stack-sm">
          <p className="eyebrow">{t("med_past")}</p>
          {past.map((m) => <Medicine key={m.dosage_id} m={m} />)}
        </section>
      )}
    </>
  );
}
