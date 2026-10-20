"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Icon } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { Avatar, ErrorState, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { homePath, setIdentity } from "@/lib/identity";
import { useT } from "@/lib/i18n";
import type { People } from "@/lib/types";

export default function WhoPage() {
  const { role } = useParams<{ role: string }>();
  const router = useRouter();
  const { t } = useT();
  const valid = role === "patient" || role === "doctor";
  const { data, error, mutate } = useApi<People>(valid ? "/api/app/people" : null, 0);

  useEffect(() => {
    if (!valid) router.replace("/");
  }, [valid, router]);

  if (!valid) return null;
  const people = role === "patient" ? data?.patients : data?.doctors;

  return (
    <main className="welcome">
      <div className="row between">
        <Link href="/" className="btn ghost sm"><Icon name="chevron-left" />{t("back")}</Link>
        <LangSwitch />
      </div>
      <h1>{t(role === "patient" ? "pick_patient" : "pick_doctor")}</h1>
      <div className="card flush" style={{ marginTop: 20 }}>
        {error ? <ErrorState onRetry={() => mutate()} /> : !people ? <Loading /> : people.length === 0 ? (
          <p className="empty">{t("nobody")}</p>
        ) : (
          <ul className="list">
            {people.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="list-item"
                  style={{ width: "100%", background: "none", border: 0, font: "inherit", textAlign: "left", cursor: "pointer", color: "inherit" }}
                  onClick={() => {
                    const identity = role === "patient" ? ({ role, id: p.id } as const) : ({ role: "doctor", id: p.id } as const);
                    setIdentity(identity);
                    router.push(homePath(identity));
                  }}
                >
                  <Avatar name={p.name} />
                  <span className="grow">
                    <strong>{p.name}</strong>
                    {p.description && <span className="small muted" style={{ display: "block" }}>{p.description}</span>}
                  </span>
                  <Icon name="chevron-right" className="chev" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
