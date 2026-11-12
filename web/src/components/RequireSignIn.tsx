"use client";

// Shows a screen only to the people it is for. Not signed in -> the sign-in page (and back here after).
// Signed in as someone else -> a plain "not yours" screen. The API refuses their data anyway; this just
// says so in words instead of an error.

import Link from "next/link";
import { useEffect, type ReactNode } from "react";
import { Icon } from "@/components/Icon";
import { Loading } from "@/components/ui";
import { toSignIn } from "@/lib/api";
import { homePath, signOut, useIdentity, type Me } from "@/lib/identity";
import { useT } from "@/lib/i18n";

export function RequireSignIn({ allow, children }: { allow: (me: Me) => boolean; children: ReactNode }) {
  const me = useIdentity();
  const { t } = useT();

  useEffect(() => {
    if (me === null) toSignIn();
  }, [me]);

  if (!me) return <div className="welcome"><Loading /></div>;
  if (allow(me)) return <>{children}</>;
  return (
    <main className="welcome">
      <h1>{t("not_allowed_title")}</h1>
      <p className="ink-2" style={{ marginBottom: 24 }}>{t("not_allowed_sub", { name: me.name })}</p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <Link href={homePath(me)} className="btn"><Icon name="home" />{t("go_home")}</Link>
        <button type="button" className="btn secondary" onClick={() => void signOut()}>
          <Icon name="logout" />{t("sign_out")}
        </button>
      </div>
    </main>
  );
}
