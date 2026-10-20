"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { Icon } from "@/components/Icon";
import { Empty, ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { dayLabel, timeOf } from "@/lib/format";
import { useT, type MessageKey } from "@/lib/i18n";
import type { AlertView, CheckinView, PatientHistory } from "@/lib/types";

type Item = { at: string; checkin?: CheckinView; alert?: AlertView };

function MedicineStatus({ status }: { status: string | null | undefined }) {
  const { t } = useT();
  if (!status) return null;
  const m: Record<string, [string, "check" | "x" | "help", MessageKey]> = {
    taken: ["good", "check", "med_status_taken"],
    not_taken: ["crit", "x", "med_status_not_taken"],
    confusion: ["", "help", "med_status_confusion"],
    dont_know: ["", "help", "med_status_dont_know"],
  };
  const [tone, icon, label] = m[status] ?? m.dont_know;
  return <span className={`chip ${tone}`}><Icon name={icon} />{t(label)}</span>;
}

export default function History() {
  const { id } = useParams<{ id: string }>();
  const { data, error, mutate } = useApi<PatientHistory>(`/api/app/patients/${id}/history`, 60_000);
  const { t, lang } = useT();

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const tz = data.timezone;
  const items: Item[] = [
    ...data.checkins.map((c) => ({ at: c.at, checkin: c })),
    ...data.alerts.map((a) => ({ at: a.at, alert: a })),
  ].sort((a, b) => b.at.localeCompare(a.at));

  return (
    <>
      <h1>{t("history_title")}</h1>
      {items.length === 0 ? (
        <div className="card"><Empty icon="history">{t("no_history")}</Empty></div>
      ) : (
        <ul className="timeline">
          {items.map((it) => {
            const c = it.checkin;
            const tone = it.alert ? "warn" : c?.doctor_connected || c?.patient_status === "urgent" ? "crit" : c?.patient_status === "remedy" ? "warn" : "good";
            return (
              <li key={(c?.call_id ?? "") + it.at + (it.alert ? "a" : "c")} className={tone}>
                <p className="when">{dayLabel(it.at, tz, lang)}, {timeOf(it.at, tz)}</p>
                {c && (
                  <div className="card" style={{ marginTop: 8 }}>
                    <p className="strong" style={{ marginBottom: 8 }}>{t("checkin")}</p>
                    <div className="row wrap" style={{ gap: 6 }}>
                      <MedicineStatus status={c.medicine_status} />
                      {c.escalated && (
                        <span className="chip crit"><Icon name="stethoscope" />{t(c.doctor_connected ? "doctor_joined" : "escalated")}</span>
                      )}
                    </div>
                    {c.symptoms.length > 0 && (
                      <p className="small ink-2" style={{ marginTop: 10 }}>{t("mentioned", { list: c.symptoms.join(", ") })}</p>
                    )}
                    {c.summary && <p className="small muted" style={{ marginTop: 6 }}>{c.summary}</p>}
                    <p style={{ marginTop: 12 }}>
                      <Link href={`/calls/${c.call_id}`} className="btn ghost sm">{t("view_conversation")}<Icon name="chevron-right" /></Link>
                    </p>
                  </div>
                )}
                {it.alert && (
                  <div className="callout warn" style={{ marginTop: 8 }}>
                    <Icon name="heart" />
                    <div>
                      <p className="strong">{t("family_told")}{it.alert.caregiver ? ` · ${it.alert.caregiver}` : ""}</p>
                      <p className="small">{it.alert.message}</p>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
