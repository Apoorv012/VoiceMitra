"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { ErrorState, Loading } from "@/components/ui";
import { api, ApiError, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import type { ContactMessage, ContactTopic, WaitlistEntry } from "@/lib/types";

const TOPIC: Record<ContactTopic, string> = {
  demo: "Demo",
  pilot: "Pilot",
  family: "Family",
  other: "Other",
};

/** Emails left on the homepage's one-field waitlist, newest first, with one button to copy them all. */
function WaitlistCard() {
  const { data, error, mutate } = useApi<WaitlistEntry[]>("/api/waitlist", 60_000);
  const [copied, setCopied] = useState(false);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(data.map((e) => e.email).join(", "));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      /* clipboard refused: the addresses are still there to select */
    }
  };

  return (
    <>
      <div className="page-head" style={{ marginTop: 32 }}>
        <div>
          <h2>Waitlist</h2>
          <p className="ink-2">From the homepage, email only · {data.length === 1 ? "1 person" : `${data.length} people`}</p>
        </div>
        {data.length > 0 && (
          <button type="button" className="btn secondary sm" onClick={copyAll} aria-live="polite">
            {copied ? <><Icon name="check" />Copied</> : "Copy all emails"}
          </button>
        )}
      </div>
      <div className="card flush">
        {data.length === 0 ? <p className="empty">Nobody yet. Emails appear here when someone joins the waitlist.</p> : (
          <ul className="list">
            {data.map((e) => (
              <li key={e.id}>
                <a className="grow" href={`mailto:${e.email}`} style={{ overflowWrap: "anywhere" }}>{e.email}</a>
                <span className="muted small">{ago(e.created_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

/** Messages sent from the homepage contact form, newest first, then the waitlist. */
export default function Messages() {
  const { data, error, mutate } = useApi<ContactMessage[]>("/api/contact", 60_000);
  const [busy, setBusy] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  if (error && !data) return <ErrorState onRetry={() => mutate()} />;
  if (!data) return <Loading />;

  const open = data.filter((m) => !m.handled).length;

  const toggle = async (m: ContactMessage) => {
    setBusy(m.id);
    setProblem(null);
    try {
      await api(`/api/contact/${m.id}/handled`, { method: "PUT", json: { handled: !m.handled } });
    } catch (err) {
      setProblem(err instanceof ApiError ? err.message : "That didn't work");
    } finally {
      setBusy(null);
      void mutate();
    }
  };

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Messages</h1>
          <p className="ink-2">
            From the homepage contact form · {open === 0 ? "all replied to" : `${open} waiting for a reply`}
          </p>
        </div>
      </div>

      {problem && <div className="callout crit" role="alert"><Icon name="alert" /><p>{problem}</p></div>}

      <div className="card flush">
        {data.length === 0 ? <p className="empty">No messages yet. They appear here when someone uses the contact form.</p> : (
          <ul className="list">
            {data.map((m) => (
              <li key={m.id} style={{ alignItems: "flex-start", flexWrap: "wrap", opacity: m.handled ? 0.6 : 1 }}>
                <div className="grow" style={{ minWidth: 220, display: "grid", gap: 4 }}>
                  <div className="row wrap" style={{ gap: 8 }}>
                    <strong>{m.name}</strong>
                    <span className="chip accent">{TOPIC[m.topic]}</span>
                    {m.handled && <span className="chip good"><Icon name="check" />Replied</span>}
                    <span className="muted small">{ago(m.created_at)}</span>
                  </div>
                  <span className="small ink-2" style={{ overflowWrap: "anywhere" }}>
                    <a href={`mailto:${m.email}`}>{m.email}</a>
                    {m.phone && <> · {m.phone}</>}
                    {m.organisation && <> · {m.organisation}</>}
                  </span>
                  <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{m.message}</p>
                </div>
                <button type="button" className="btn secondary sm" disabled={busy === m.id} onClick={() => toggle(m)}>
                  {m.handled ? "Mark as waiting" : <><Icon name="check" />Mark replied</>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <WaitlistCard />
    </>
  );
}
