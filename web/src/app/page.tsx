"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { Loading } from "@/components/ui";
import { homePath, setIdentity, useIdentity } from "@/lib/identity";
import { useT, type MessageKey } from "@/lib/i18n";

function Choice({
  icon, title, sub, href, onClick,
}: { icon: IconName; title: MessageKey; sub: MessageKey; href?: string; onClick?: () => void }) {
  const { t } = useT();
  const body = (
    <>
      <span className="ico"><Icon name={icon} /></span>
      <span className="grow">
        <strong>{t(title)}</strong>
        <span className="small ink-2" style={{ display: "block" }}>{t(sub)}</span>
      </span>
      <Icon name="chevron-right" className="chev" />
    </>
  );
  return href ? (
    <Link href={href} className="choice">{body}</Link>
  ) : (
    <button type="button" className="choice" onClick={onClick} style={{ width: "100%", textAlign: "left", font: "inherit", cursor: "pointer" }}>
      {body}
    </button>
  );
}

export default function Welcome() {
  const identity = useIdentity();
  const router = useRouter();
  const { t } = useT();

  // Someone who already chose is taken straight to their own home (this is what an installed app opens).
  useEffect(() => {
    if (identity) router.replace(homePath(identity));
  }, [identity, router]);

  if (identity === undefined || identity) {
    return <div className="welcome"><Loading /></div>;
  }

  return (
    <main className="welcome">
      <div className="row between">
        <span className="brand-mark"><Icon name="mic" /></span>
        <LangSwitch />
      </div>
      <h1>{t("who_title")}</h1>
      <p className="ink-2" style={{ marginBottom: 24 }}>{t("who_sub")}</p>
      <div className="stack-sm">
        <Choice icon="user" title="role_patient" sub="role_patient_sub" href="/who/patient" />
        <Choice icon="stethoscope" title="role_doctor" sub="role_doctor_sub" href="/who/doctor" />
        <Choice
          icon="building" title="role_operator" sub="role_operator_sub"
          onClick={() => {
            setIdentity({ role: "operator" });
            router.push("/operator");
          }}
        />
      </div>
    </main>
  );
}
