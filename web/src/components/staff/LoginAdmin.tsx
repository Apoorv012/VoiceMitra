"use client";

// Staff set the username + password a patient or a family contact signs in with, and pass them on.
// The password is shown once, right after saving (only a hash is stored).

import { useId, useState, type FormEvent } from "react";
import { Icon } from "@/components/Icon";
import { ApiError, api, useApi } from "@/lib/api";
import type { components } from "@/lib/api-schema";

type LoginView = components["schemas"]["LoginView"];

const MIN_PASSWORD = 6;
const MIN_USERNAME = 3;
// No look-alikes (0/o, 1/l/i): these get read out over the phone.
const ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789";

function makePassword(length = 10): string {
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join("");
}

function suggestUsername(name: string): string {
  return name.trim().split(/\s+/)[0]?.toLowerCase().replace(/[^a-z0-9]/g, "") ?? "";
}

export function LoginAdmin({
  url, title, sub, personName,
}: { url: string; title: string; sub: string; personName: string }) {
  const ids = useId();
  const login = useApi<LoginView>(url, 0);
  const current = login.data?.username ?? null;
  const notSet = login.error instanceof ApiError && login.error.status === 404;

  const [editing, setEditing] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [handOver, setHandOver] = useState<{ username: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  function start() {
    setUsername(current ?? suggestUsername(personName));
    setPassword(makePassword());
    setProblem(null);
    setHandOver(null);
    setEditing(true);
  }

  async function save(e: FormEvent) {
    e.preventDefault();
    const name = username.trim();
    if (name.length < MIN_USERNAME) return setProblem(`The username needs at least ${MIN_USERNAME} characters.`);
    if (password.length < MIN_PASSWORD) return setProblem(`The password needs at least ${MIN_PASSWORD} characters.`);
    setBusy(true);
    setProblem(null);
    try {
      await api(url, { method: "PUT", json: { username: name, password } });
      await login.mutate({ username: name }, { revalidate: true });
      setHandOver({ username: name, password });
      setEditing(false);
    } catch (err) {
      setProblem(err instanceof ApiError && err.status === 409
        ? "Someone else already has this username. Pick another."
        : "Couldn't save. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Remove ${personName}'s login? They are signed out of the website. Phones already signed in stay connected.`)) return;
    setBusy(true);
    try {
      await api(url, { method: "DELETE" });
      await login.mutate(undefined, { revalidate: true });
      setHandOver(null);
    } catch {
      setProblem("Couldn't remove the login. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" aria-labelledby={`${ids}-title`}>
      <h3 id={`${ids}-title`}>{title}</h3>
      <p className="small ink-2" style={{ margin: "4px 0 12px" }}>{sub}</p>

      {!editing && current && <p style={{ marginBottom: 12 }}>Username: <strong translate="no">{current}</strong></p>}
      {!editing && notSet && <p className="small muted" style={{ marginBottom: 12 }}>No login yet: they can&apos;t sign in.</p>}
      {login.error && !notSet && <p className="small" role="alert">Couldn&apos;t load the login.</p>}

      {handOver && !editing && (
        <div className="callout good" role="status" style={{ marginBottom: 12 }}>
          <Icon name="check" />
          <div>
            <p className="strong">Saved. Give {personName} these (the password is shown only now):</p>
            <p translate="no" style={{ fontFamily: "ui-monospace, monospace" }}>
              username {handOver.username} · password {handOver.password}
            </p>
            <button
              type="button" className="btn ghost sm" style={{ marginTop: 6 }}
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(`Username: ${handOver.username}\nPassword: ${handOver.password}`);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1800);
                } catch {
                  /* clipboard refused: the text is still there to select */
                }
              }}
            >
              <Icon name={copied ? "check" : "file"} />{copied ? "Copied" : "Copy both"}
            </button>
          </div>
        </div>
      )}

      {editing ? (
        <form onSubmit={(e) => void save(e)} noValidate className="stack-sm">
          <div className="field">
            <label htmlFor={`${ids}-user`}>Username</label>
            <input
              id={`${ids}-user`} type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} maxLength={40} required
            />
          </div>
          <div className="field">
            <label htmlFor={`${ids}-pass`}>{current ? "New password" : "Password"}</label>
            <div className="row" style={{ gap: 8 }}>
              <input
                id={`${ids}-pass`} className="grow" type="text" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete="off" autoCapitalize="none" autoCorrect="off" spellCheck={false} maxLength={200} required
              />
              <button type="button" className="btn ghost sm" onClick={() => setPassword(makePassword())}>New one</button>
            </div>
            <span className="hint">Shown in full so you can pass it on. At least {MIN_PASSWORD} characters.</span>
          </div>
          {problem && <div className="callout crit" role="alert"><Icon name="alert" /><p>{problem}</p></div>}
          <div className="row" style={{ gap: 8 }}>
            <button type="submit" className="btn" disabled={busy}>Save login</button>
            <button type="button" className="btn secondary" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
          </div>
        </form>
      ) : (
        (current || notSet) && (
          <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn" onClick={start}>{current ? "Change login" : "Set a login"}</button>
            {current && <button type="button" className="btn ghost" disabled={busy} onClick={() => void remove()}>Remove login</button>}
          </div>
        )
      )}
      {!editing && problem && <p className="small" role="alert" style={{ marginTop: 8 }}>{problem}</p>}
    </div>
  );
}
