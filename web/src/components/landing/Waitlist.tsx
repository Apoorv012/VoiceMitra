"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import { CONTACT_EMAIL } from "./ContactForm";
import s from "./landing.module.css";

/** The homepage's one-field waitlist: an email and a button. Saved by POST /api/waitlist; operators see the list
 * on /operator/messages. The longer contact form further down is for demos and questions. */
export function Waitlist() {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [joined, setJoined] = useState<string | null>(null);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = String(data.get("email") ?? "").trim();
    setBusy(true);
    setProblem(null);
    try {
      await api("/api/waitlist", {
        method: "POST",
        json: { email, website: String(data.get("website") ?? "").trim() || null },
      });
      setJoined(email);
    } catch (err) {
      setProblem(
        err instanceof ApiError && err.status === 422 ? "That doesn't look like an email address."
          : err instanceof ApiError && err.status === 429 ? `Too many sign-ups right now. Try again in a few minutes, or email ${CONTACT_EMAIL}.`
            : `That didn't go through. Check your connection and try again, or email ${CONTACT_EMAIL}.`,
      );
    } finally {
      setBusy(false);
    }
  };

  if (joined) {
    return (
      <div className={s.wl} id="waitlist" role="status">
        <p className={s.wlDone}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m5 12.5 4.5 4.5L19 7.5" />
          </svg>
          <span>You&apos;re on the list. We&apos;ll email <strong>{joined}</strong> when there&apos;s a spot.</span>
        </p>
      </div>
    );
  }

  return (
    <form className={s.wl} id="waitlist" onSubmit={submit}>
      <div className={s.wlRow}>
        <label className={s.srOnly} htmlFor="waitlist-email">Email address</label>
        <input
          className={s.wlInput} id="waitlist-email" name="email" type="email" required maxLength={200}
          autoComplete="email" inputMode="email" placeholder="you@example.com"
        />
        <button type="submit" className={`${s.b} ${s.lg} ${s.dark}`} disabled={busy}>
          {busy ? "Joining…" : "Join the waitlist"}
        </button>
      </div>
      {/* A person never sees or fills this; simple bots do, and the backend drops those sign-ups. */}
      <div className={s.hp} aria-hidden="true">
        <label htmlFor="waitlist-website">Website</label>
        <input id="waitlist-website" name="website" tabIndex={-1} autoComplete="off" />
      </div>
      {problem
        ? <p className={s.wlProblem} role="alert">{problem}</p>
        : <p className={s.wlNote}>Now in a small pilot. Just your email; we&apos;ll write when there&apos;s a spot for you.</p>}
    </form>
  );
}
