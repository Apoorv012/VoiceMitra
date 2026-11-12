"use client";

// "Your login" on the patient's Me tab: the username + password they sign in with, here and in the VoiceMitra
// phone app (the same login). Staff set the first one; the patient can change it here. Shows the current
// username, never the password (it isn't stored).

import { useId, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { ApiError, api, useApi } from "@/lib/api";
import type { components } from "@/lib/api-schema";
import { useT, type MessageKey } from "@/lib/i18n";

type LoginView = components["schemas"]["LoginView"];

const MIN_PASSWORD = 6;
const MIN_USERNAME = 3;

export function PhoneLogin({ patientId }: { patientId: string }) {
  const { t } = useT();
  const ids = useId();
  const login = useApi<LoginView>(`/api/patients/${patientId}/login`, 0);
  // 404 = no login yet; anything else that failed is a real error.
  const current = login.data?.username ?? null;
  const notSet = login.error instanceof ApiError && login.error.status === 404;

  const [editing, setEditing] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<MessageKey | null>(null);
  const [saved, setSaved] = useState(false);

  function startEditing() {
    setUsername(current ?? "");
    setPassword("");
    setShow(false);
    setProblem(null);
    setSaved(false);
    setEditing(true);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    if (username.trim().length < MIN_USERNAME) return setProblem("login_short_user");
    if (password.length < MIN_PASSWORD) return setProblem("login_short_pass");
    setBusy(true);
    setProblem(null);
    try {
      await api(`/api/patients/${patientId}/login`, { method: "PUT", json: { username: username.trim(), password } });
      await login.mutate({ username: username.trim() }, { revalidate: true });
      setEditing(false);
      setPassword("");
      setSaved(true);
    } catch (err) {
      setProblem(err instanceof ApiError && err.status === 409 ? "login_taken" : "login_error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-labelledby={`${ids}-title`}>
      <div className="row top">
        <Icon name="user" className="lg" />
        <div className="grow">
          <h2 id={`${ids}-title`}>{t("login_title")}</h2>
          <p className="small ink-2" style={{ margin: "4px 0 12px" }}>{t("login_sub")}</p>

          {!editing && current && (
            <p style={{ marginBottom: 12 }}>
              <span className="small muted" style={{ display: "block" }}>{t("login_username")}</span>
              <strong translate="no">{current}</strong>
            </p>
          )}
          {!editing && notSet && <p className="small muted" style={{ marginBottom: 12 }}>{t("login_none")}</p>}

          {saved && !editing && (
            <div className="callout good" role="status" style={{ marginBottom: 12 }}>
              <Icon name="check" /><p>{t("login_saved")}</p>
            </div>
          )}

          {login.error && !notSet && !editing && (
            <div className="callout crit" role="alert" style={{ marginBottom: 12 }}>
              <Icon name="alert" /><p>{t("load_error")}</p>
            </div>
          )}

          {editing ? (
            <form onSubmit={(e) => void save(e)} noValidate style={{ display: "grid", gap: 12 }}>
              <div className="field">
                <label htmlFor={`${ids}-user`}>{t("login_username")}</label>
                <input
                  id={`${ids}-user`}
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="off"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  maxLength={40}
                  required
                />
              </div>
              <div className="field">
                <label htmlFor={`${ids}-pass`}>{current ? t("login_new_password") : t("login_password")}</label>
                <input
                  id={`${ids}-pass`}
                  type={show ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  maxLength={200}
                  aria-describedby={`${ids}-hint`}
                  required
                />
                <span id={`${ids}-hint`} className="hint">{t("login_pass_hint", { n: MIN_PASSWORD })}</span>
                <label className="small row" style={{ gap: 8, fontWeight: 400 }}>
                  <input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} />
                  {t("login_show")}
                </label>
              </div>

              {problem && (
                <div className="callout crit" role="alert">
                  <Icon name="alert" /><p>{t(problem, { n: problem === "login_short_user" ? MIN_USERNAME : MIN_PASSWORD })}</p>
                </div>
              )}

              <div className="row" style={{ gap: 8 }}>
                <button type="submit" className="btn" disabled={busy}>{t("login_save")}</button>
                <button type="button" className="btn secondary" disabled={busy} onClick={() => setEditing(false)}>
                  {t("login_cancel")}
                </button>
              </div>
            </form>
          ) : (
            (current || notSet) && (
              <button type="button" className="btn" onClick={startEditing}>
                {current ? t("login_change") : t("login_set")}
              </button>
            )
          )}
        </div>
      </div>
    </section>
  );
}
