"use client";

import { useParams, useRouter } from "next/navigation";
import { Icon } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { Avatar, ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { clearIdentity } from "@/lib/identity";
import { useT } from "@/lib/i18n";
import { useInstall } from "@/lib/install";
import type { PatientHome } from "@/lib/types";

export default function Me() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { t } = useT();
  const install = useInstall();
  const { data, error, mutate } = useApi<PatientHome>(`/api/app/patients/${id}/home`, 0);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const { patient, caregiver, allergies } = data;

  return (
    <>
      <div className="row" style={{ gap: 16 }}>
        <Avatar name={patient.name} size="lg" />
        <div>
          <h1>{patient.name}</h1>
          <p className="ink-2">{t("years_old", { n: patient.age ?? "" })}</p>
        </div>
      </div>

      <section className="card flush">
        <ul className="list">
          <li>
            <Icon name="globe" />
            <span className="grow strong">{t("language")}</span>
            <LangSwitch />
          </li>
          {caregiver && (
            <li>
              <Icon name="heart" />
              <span className="grow">
                <span className="small muted" style={{ display: "block" }}>{t("caregiver")}</span>
                <strong>{caregiver.name}</strong> <span className="ink-2">({caregiver.relation})</span>
              </span>
            </li>
          )}
          <li>
            <Icon name="shield" />
            <span className="grow">
              <span className="small muted" style={{ display: "block" }}>{t("allergies")}</span>
              {allergies.length ? allergies.join(", ") : t("no_allergies")}
            </span>
          </li>
        </ul>
      </section>

      {!install.installed && (install.canPrompt || install.showIosSteps) && (
        <section className="card">
          <div className="row top">
            <Icon name="phone" className="lg" />
            <div className="grow">
              <h2>{t("install_title")}</h2>
              <p className="small ink-2" style={{ margin: "4px 0 12px" }}>
                {install.showIosSteps ? t("install_ios") : t("install_sub")}
              </p>
              {install.canPrompt && <button type="button" className="btn" onClick={() => void install.prompt()}>{t("install_btn")}</button>}
            </div>
          </div>
        </section>
      )}

      <button
        type="button"
        className="btn secondary block"
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
