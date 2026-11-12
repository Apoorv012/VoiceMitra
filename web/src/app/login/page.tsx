"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useId, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { Loading } from "@/components/ui";
import { ApiError } from "@/lib/api";
import { afterSignIn, signIn, useIdentity } from "@/lib/identity";
import { useT, type MessageKey } from "@/lib/i18n";

function SignIn() {
  const me = useIdentity();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const { t } = useT();
  const ids = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<MessageKey | null>(null);

  // Someone already signed in goes straight to their page (this is what an installed app opens).
  useEffect(() => {
    if (me) router.replace(afterSignIn(me, next));
  }, [me, next, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!username.trim() || !password) return setProblem("signin_wrong");
    setBusy(true);
    setProblem(null);
    try {
      const who = await signIn(username.trim(), password);
      router.replace(afterSignIn(who, next));
    } catch (err) {
      setProblem(err instanceof ApiError ? (err.status === 429 ? "signin_paused" : err.status === 401 ? "signin_wrong"
        : "signin_error") : "signin_error");
      setBusy(false);
    }
  }

  if (me === undefined || me) return <div className="welcome"><Loading /></div>;

  return (
    <main className="welcome">
      <div className="row between">
        <Link href="/" className="brand-mark" aria-label="VoiceMitra home"><Icon name="mic" /></Link>
        <LangSwitch />
      </div>
      <h1>{t("signin_title")}</h1>
      <p className="ink-2" style={{ marginBottom: 24 }}>{t("signin_sub")}</p>

      <form className="card" onSubmit={(e) => void submit(e)} noValidate style={{ display: "grid", gap: 16 }}>
        <div className="field">
          <label htmlFor={`${ids}-user`}>{t("login_username")}</label>
          <input
            id={`${ids}-user`}
            name="username"
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            maxLength={200}
            required
            autoFocus
          />
        </div>
        <div className="field">
          <label htmlFor={`${ids}-pass`}>{t("login_password")}</label>
          <input
            id={`${ids}-pass`}
            name="password"
            type={show ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
            maxLength={200}
            required
          />
          <label className="small row" style={{ gap: 8, fontWeight: 400 }}>
            <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
            {t("login_show")}
          </label>
        </div>

        {problem && (
          <div className="callout crit" role="alert">
            <Icon name="alert" /><p>{t(problem)}</p>
          </div>
        )}

        <button type="submit" className="btn block" disabled={busy}>{t("signin_btn")}</button>
        <p className="small muted" style={{ margin: 0 }}>{t("signin_forgot")}</p>
      </form>

      <div className="card" style={{ marginTop: 16 }}>
        <p className="ink-2" style={{ margin: "0 0 8px" }}>{t("signin_no_account")}</p>
        <Link href="/?topic=pilot#contact" className="btn secondary">
          <Icon name="send" />{t("signin_early_access")}
        </Link>
      </div>
    </main>
  );
}

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary in a statically rendered page.
  return (
    <Suspense fallback={<div className="welcome"><Loading /></div>}>
      <SignIn />
    </Suspense>
  );
}
