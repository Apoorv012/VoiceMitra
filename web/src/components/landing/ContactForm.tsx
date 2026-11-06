"use client";

import { useState, type FormEvent } from "react";
import { api, ApiError } from "@/lib/api";
import type { ContactTopic } from "@/lib/types";
import s from "./landing.module.css";

export const CONTACT_EMAIL = "apoorvmittal125@gmail.com";

const TOPICS: { value: ContactTopic; label: string; hint: string }[] = [
  { value: "demo", label: "Book a demo", hint: "When suits you, and what you'd like to see." },
  { value: "pilot", label: "Run a pilot", hint: "Your clinic, roughly how many patients, and which languages." },
  { value: "family", label: "Set up for family", hint: "Who it's for, and what medicines they take." },
  { value: "other", label: "Something else", hint: "How can we help?" },
];

/** The email address as selectable text, with a copy button (mailto links don't open everywhere). */
export function CopyEmail() {
  const [copied, setCopied] = useState(false);
  return (
    <div className={s.mail}>
      <span>Or email us directly</span>
      <div className={s.mailRow}>
        <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        <button
          type="button"
          className={s.copy}
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(CONTACT_EMAIL);
              setCopied(true);
              setTimeout(() => setCopied(false), 1800);
            } catch {
              /* clipboard refused: the address is still there to select */
            }
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

type Sent = { name: string; email: string };

/** The homepage contact form. Messages are saved by the backend (POST /api/contact) and read by operators. */
export function ContactForm() {
  const [topic, setTopic] = useState<ContactTopic>("demo");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent | null>(null);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    const field = (name: string) => String(data.get(name) ?? "").trim();
    setBusy(true);
    setProblem(null);
    try {
      await api("/api/contact", {
        method: "POST",
        json: {
          topic,
          name: field("name"),
          email: field("email"),
          phone: field("phone") || null,
          organisation: field("organisation") || null,
          message: field("message"),
          website: field("website") || null,
        },
      });
      setSent({ name: field("name"), email: field("email") });
      form.reset();
    } catch (err) {
      const why = err instanceof ApiError && err.status === 429
        ? "Too many messages right now. Please try again in a few minutes."
        : err instanceof ApiError && err.status === 422
          ? "Please check your email address and fill in the required fields."
          : "Your message didn't send. Check your connection and try again.";
      setProblem(`${why} You can also email ${CONTACT_EMAIL}.`);
    } finally {
      setBusy(false);
    }
  };

  if (sent) {
    return (
      <div className={s.form} role="status">
        <div className={s.done}>
          <h3>Thanks, {sent.name}.</h3>
          <p>Your message has been sent. We&apos;ll reply to <strong>{sent.email}</strong>.</p>
          <button type="button" className={`${s.b} ${s.ghost}`} onClick={() => setSent(null)}>Send another message</button>
        </div>
      </div>
    );
  }

  const hint = TOPICS.find((t) => t.value === topic)?.hint ?? "";

  return (
    <form className={s.form} onSubmit={submit}>
      <fieldset className={s.fieldset}>
        <legend className={s.legend}>What would you like to do?</legend>
        <div className={s.topics}>
          {TOPICS.map((t) => (
            <label key={t.value} className={s.topic}>
              <input
                type="radio" name="topic" id={`contact-topic-${t.value}`} value={t.value}
                checked={topic === t.value} onChange={() => setTopic(t.value)}
              />
              <span>{t.label}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <div className={s.grid2}>
        <div className={s.field}>
          <label className={s.label} htmlFor="contact-name">Your name</label>
          <input className={s.input} id="contact-name" name="name" required maxLength={100} autoComplete="name" />
        </div>
        <div className={s.field}>
          <label className={s.label} htmlFor="contact-email">Email</label>
          <input className={s.input} id="contact-email" name="email" type="email" required maxLength={200} autoComplete="email" />
        </div>
        <div className={s.field}>
          <label className={s.label} htmlFor="contact-phone">Phone <span className={s.opt}>(optional)</span></label>
          <input className={s.input} id="contact-phone" name="phone" type="tel" maxLength={30} autoComplete="tel" />
        </div>
        <div className={s.field}>
          <label className={s.label} htmlFor="contact-org">Hospital or clinic <span className={s.opt}>(optional)</span></label>
          <input className={s.input} id="contact-org" name="organisation" maxLength={150} autoComplete="organization" />
        </div>
      </div>

      <div className={s.field}>
        <label className={s.label} htmlFor="contact-message">Message</label>
        <textarea className={s.input} id="contact-message" name="message" required maxLength={4000} placeholder={hint} />
      </div>

      {/* A person never sees or fills this; simple bots do, and the backend drops those messages. */}
      <div className={s.hp} aria-hidden="true">
        <label htmlFor="contact-website">Website</label>
        <input id="contact-website" name="website" tabIndex={-1} autoComplete="off" />
      </div>

      {problem && <p className={s.problem} role="alert">{problem}</p>}

      <div className={s.formFoot}>
        <p className={s.fine}>We only use these details to reply to you.</p>
        <button type="submit" className={`${s.b} ${s.lg} ${s.dark}`} disabled={busy}>
          {busy ? "Sending…" : "Send message"}
        </button>
      </div>
    </form>
  );
}
