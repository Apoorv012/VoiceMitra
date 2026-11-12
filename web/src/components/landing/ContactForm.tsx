"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError } from "@/lib/api";
import type { ContactTopic } from "@/lib/types";
import s from "./landing.module.css";

export const CONTACT_EMAIL = "apoorvmittal125@gmail.com";

const TOPICS: { value: ContactTopic; label: string; hint: string }[] = [
  { value: "demo", label: "Book a demo", hint: "When suits you, and what you'd like to see." },
  // Also where "ask to join / early access" links land (/?topic=pilot#contact): there are no sign-ups.
  { value: "pilot", label: "Join the pilot", hint: "Early access for your clinic or your family: who it's for, roughly how many patients, and which languages." },
  { value: "family", label: "Set up for family", hint: "Who it's for, and what medicines they take." },
  { value: "other", label: "Something else", hint: "How can we help?" },
];

/** The email address as selectable text, with a copy button (mailto links don't open everywhere). */
export function CopyEmail() {
  const [copied, setCopied] = useState(false);
  return (
    <div className={s.mail}>
      <span className={s.mailIcon} aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="3" />
          <path d="m4 7 8 6 8-6" />
        </svg>
      </span>
      <div className={s.mailText}>
        <span className={s.mailLabel}>Or email us directly</span>
        <a className={s.mailAddr} href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
      </div>
      <button
        type="button"
        className={`${s.copy} ${copied ? s.copied : ""}`}
        aria-live="polite"
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
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {copied ? <path d="m5 12.5 4.5 4.5L19 7.5" /> : <><rect x="8" y="8" width="12" height="12" rx="2.5" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>}
        </svg>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

type Sent = { name: string; email: string };

const TOPIC_EVENT = "vm:contact-topic";

/** A link to the form that also picks its topic (e.g. "Join the pilot" from the hero's early-access line). */
export function TopicLink({ topic, children }: { topic: ContactTopic; children: ReactNode }) {
  return (
    <a href="#contact" onClick={() => window.dispatchEvent(new CustomEvent(TOPIC_EVENT, { detail: topic }))}>
      {children}
    </a>
  );
}

/** The homepage contact form. Messages are saved by the backend (POST /api/contact) and read by operators. */
export function ContactForm() {
  const [topic, setTopic] = useState<ContactTopic>("demo");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sent, setSent] = useState<Sent | null>(null);

  // A link can pick the topic: /?topic=pilot#contact from another page (the sign-in page's "ask for early
  // access"), or a TopicLink on this one.
  useEffect(() => {
    const pick = (asked: unknown) => {
      const match = TOPICS.find((t) => t.value === asked);
      if (match) setTopic(match.value);
    };
    pick(new URLSearchParams(window.location.search).get("topic"));
    const onPick = (e: Event) => pick((e as CustomEvent).detail);
    window.addEventListener(TOPIC_EVENT, onPick);
    return () => window.removeEventListener(TOPIC_EVENT, onPick);
  }, []);

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
