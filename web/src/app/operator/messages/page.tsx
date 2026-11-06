"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { ErrorState, Loading } from "@/components/ui";
import { api, ApiError, useApi } from "@/lib/api";
import { ago } from "@/lib/format";
import type { ContactMessage, ContactTopic } from "@/lib/types";

const TOPIC: Record<ContactTopic, string> = {
  demo: "Demo",
  pilot: "Pilot",
  family: "Family",
  other: "Other",
};

/** Messages sent from the homepage contact form, newest first. */
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
    </>
  );
}
