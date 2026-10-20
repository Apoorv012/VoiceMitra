"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { Adherence, WeekDots } from "@/components/staff/parts";
import { ErrorState, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useApi } from "@/lib/api";
import type { ChatMessage, EscalationEvent, VoiceJoin } from "@/lib/events";
import { ago, clockLabel } from "@/lib/format";
import { useVoiceRoom } from "@/lib/useVoiceRoom";
import { useSocket } from "@/lib/ws";
import type { EscalationView } from "@/lib/types";

type Msg = ChatMessage;
type Join = VoiceJoin;
const ENDED = ["summarising", "resolved", "abandoned"];

function Steps({ status }: { status: string }) {
  const at = status === "merged" ? 1 : ENDED.includes(status) ? 2 : 0;
  const steps = ["Briefing", "On the call", "Summary"];
  return (
    <div className="steps" aria-label="Call progress">
      {steps.map((s, i) => (
        <span key={s} style={{ display: "contents" }}>
          {i > 0 && <span className="sep" aria-hidden="true">›</span>}
          <span className={`step ${i < at ? "done" : i === at ? "on" : ""}`} aria-current={i === at ? "step" : undefined}>
            <span className="n">{i < at ? <Icon name="check" /> : i + 1}</span>{s}
          </span>
        </span>
      ))}
    </div>
  );
}

export default function EscalationCall() {
  const { id, eid } = useParams<{ id: string; eid: string }>();
  const { data: view, error: viewError, mutate } = useApi<EscalationView>(`/api/app/doctors/${id}/escalations/${eid}`, 0);

  const [status, setStatus] = useState("briefing");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [summary, setSummary] = useState<string | null>(null);
  const [briefJoin, setBriefJoin] = useState<Join | null>(null);
  const [mergedJoin, setMergedJoin] = useState<Join | null>(null);
  const [gone, setGone] = useState(false);
  const [text, setText] = useState("");
  const [ending, setEnding] = useState(false);
  const voice = useVoiceRoom();
  const logRef = useRef<HTMLDivElement>(null);
  const shown = useRef(0);

  const addMessage = useCallback((m: Msg) => {
    if (m.index < shown.current) return; // the snapshot and live events can overlap
    shown.current = m.index + 1;
    setMessages((prev) => [...prev, m]);
  }, []);

  const onEvent = useCallback((e: EscalationEvent) => {
    switch (e.type) {
      case "snapshot":
        setStatus(e.status);
        setSummary(e.summary ?? null);
        (e.messages ?? []).forEach(addMessage);
        if (e.brief_join && e.status === "briefing") setBriefJoin(e.brief_join);
        if (e.voice_join && e.status === "merged") setMergedJoin(e.voice_join);
        return;
      case "message":
        addMessage(e);
        return;
      case "brief_join":
        setBriefJoin({ url: e.url, token: e.token });
        return;
      case "voice_join":
        setBriefJoin(null);
        setMergedJoin({ url: e.url, token: e.token });
        return;
      case "status":
        setStatus(e.status);
        if (e.summary) setSummary(e.summary);
        if (ENDED.includes(e.status)) {
          voice.leave();
          void mutate();
        }
        return;
      case "gone":
        setGone(true);
        return;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [addMessage, mutate]);

  const { send, connected } = useSocket<EscalationEvent>(`/ws/escalations/${eid}`, onEvent);

  // Once merged, move from the briefing room into the patient's. The microphone permission was
  // normally granted for the briefing, so this joins on its own; if it can't, the button below retries.
  useEffect(() => {
    if (mergedJoin && voice.kind !== "merged" && voice.status !== "joining" && voice.status !== "error") {
      void voice.join("merged", mergedJoin.url, mergedJoin.token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mergedJoin]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  // A call that is no longer live has no socket feed, so what's shown comes from the saved record.
  const current = gone && view ? view.status : status;
  const active = !ENDED.includes(current) && !gone;
  const savedSummary = summary ?? view?.summary ?? null;
  const inMergedVoice = voice.kind === "merged";
  const pendingJoin = mergedJoin ?? briefJoin;
  const pendingKind = mergedJoin ? "merged" : "brief";
  const needsButton = active && pendingJoin && voice.kind !== pendingKind && voice.status !== "joining";

  const reply = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !send({ type: "reply", text: text.trim() })) return;
    setText("");
  };

  if (viewError && !view) return <ErrorState onRetry={() => mutate()} />;
  if (!view) return <Loading />;
  const tz = view.timezone;

  return (
    <>
      <Link href={`/doctors/${id}`} className="crumb"><Icon name="chevron-left" />Overview</Link>
      <div className="page-head">
        <div>
          <h1>Call — {view.patient.name}</h1>
          <p className="ink-2">{view.patient.age} years · {view.phone_number} · escalated {ago(view.created_at)}</p>
        </div>
        <Steps status={current} />
      </div>

      <div className="two-col">
        <div className="stack">
          {active && (
            <div className={`callout ${status === "merged" ? "good" : "accent"}`}>
              <Icon name={status === "merged" ? "phone" : "stethoscope"} />
              <p>
                {status === "merged"
                  ? `You're talking to ${view.patient.name}. VoiceMitra is listening and taking notes.`
                  : `Private line with VoiceMitra. ${view.patient.name} is on hold until you ask to merge.`}
              </p>
            </div>
          )}

          {(needsButton || voice.status === "joining" || voice.status === "error" || voice.status === "live") && active && (
            <div className="card row wrap" style={{ gap: 14 }}>
              <span className={voice.status === "live" ? "pulse" : ""}>
                <span className="avatar" style={voice.status === "live" ? { background: "var(--good-soft)", color: "var(--good-ink)" } : undefined}><Icon name="mic" /></span>
              </span>
              <div className="grow">
                {voice.status === "live" && <p><strong>Your microphone is live.</strong> {inMergedVoice ? `Speak to ${view.patient.name}.` : "Talk to VoiceMitra, or type below."}</p>}
                {voice.status === "joining" && <p>Connecting voice…</p>}
                {voice.status === "error" && <p role="alert" className="strong" style={{ color: "var(--crit-ink)" }}>{voice.error}</p>}
                {voice.status === "idle" && needsButton && <p><strong>Use your voice.</strong> {pendingKind === "merged" ? `Join the call with ${view.patient.name}.` : "Hear the briefing and answer by voice. Typing still works."}</p>}
              </div>
              {needsButton && voice.status !== "live" && (
                <button type="button" className="btn" onClick={() => void voice.join(pendingKind, pendingJoin!.url, pendingJoin!.token)}>
                  <Icon name="mic" />{voice.status === "error" ? "Try again" : pendingKind === "merged" ? "Join voice call" : "Join voice briefing"}
                </button>
              )}
              {voice.needsSoundTap && <button type="button" className="btn secondary" onClick={voice.enableSound}><Icon name="sound" />Tap to hear</button>}
            </div>
          )}

          <div className="card">
            <div className="chat convo" ref={logRef} aria-live="polite">
              {messages.length === 0 && (
                <p className="muted small" style={{ textAlign: "center" }}>
                  {gone || !active ? "This conversation isn't shown live any more. The full transcript is in the call log." : connected ? "Waiting for VoiceMitra…" : "Connecting…"}
                </p>
              )}
              {messages.map((m) => (
                <div key={m.index} className={`bubble ${m.role === "user" ? "me" : m.role === "patient" ? "patient" : m.role === "system" ? "note" : ""}`}>
                  {m.role === "agent" && <div className="who">VoiceMitra</div>}
                  {m.role === "patient" && <div className="who">{view.patient.name}</div>}
                  {m.text}
                </div>
              ))}
            </div>
            {active && !inMergedVoice && (
              <form className="row" style={{ marginTop: 12 }} onSubmit={reply} autoComplete="off">
                <input
                  type="text" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} className="grow"
                  placeholder={status === "merged" ? `Message to ${view.patient.name}` : "Ask VoiceMitra about the case, or say “merge me in”"}
                  aria-label="Message"
                />
                <button type="submit" className="btn" aria-label="Send"><Icon name="send" /></button>
              </form>
            )}
          </div>

          {active && (
            <div>
              <button type="button" className="btn danger" disabled={ending} onClick={async () => {
                setEnding(true);
                try { await api(`/api/escalations/${eid}/end`, { method: "POST" }); } finally { setEnding(false); }
              }}>
                <Icon name="phone-off" />End call
              </button>
            </div>
          )}

          {(savedSummary || ENDED.includes(current) || gone) && (
            <div className="card">
              <div className="row between"><h2>Call summary</h2>{current === "summarising" && <span className="chip"><Icon name="clock" />Writing…</span>}</div>
              <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>
                {savedSummary ?? (current === "abandoned" ? "The call ended before the patient was connected." : current === "summarising" ? "VoiceMitra is writing the summary…" : "No summary was recorded for this call.")}
              </p>
              <p style={{ marginTop: 12 }}>
                <Link href={`/calls/${view.call_id}`} className="btn ghost sm">Full call log<Icon name="chevron-right" /></Link>{" "}
                <Link href={`/doctors/${id}/patients/${view.patient.id}`} className="btn ghost sm">Patient record<Icon name="chevron-right" /></Link>
              </p>
            </div>
          )}
        </div>

        <aside className="stack" aria-label="Patient">
          <div className="callout crit"><Icon name="alert" /><div><p className="strong">Why this was escalated</p><p>{view.reason}</p></div></div>
          <div className={`callout ${view.allergies.length ? "warn" : ""}`}>
            <Icon name="shield" /><div><p className="strong">Allergies</p><p>{view.allergies.length ? view.allergies.join(", ") : "None known"}</p></div>
          </div>
          <div className="card">
            <p className="eyebrow" style={{ marginBottom: 8 }}>Current medicines</p>
            {view.medicines.length === 0 ? <p className="muted small">None on file.</p> : (
              <ul className="stack-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {view.medicines.map((m) => (
                  <li key={m.dosage_id}><strong>{m.name}</strong> <span className="ink-2 small">{m.dose} · {m.times.map(clockLabel).join(", ") || "daily"}</span></li>
                ))}
              </ul>
            )}
            <div className="row between" style={{ marginTop: 14 }}>
              <span className="small muted">Last 7 days</span>
              <WeekDots states={view.week.map((d) => d.state)} />
              <Adherence a={view.adherence} compact />
            </div>
          </div>
          {view.recent_logs.length > 0 && (
            <div className="card">
              <p className="eyebrow" style={{ marginBottom: 8 }}>Recent reports</p>
              <ul className="stack-sm" style={{ listStyle: "none", margin: 0, padding: 0 }}>
                {view.recent_logs.map((l) => (
                  <li key={l.id} className="small">
                    <span className={`chip ${l.band === "urgent" ? "crit" : l.band === "watch" ? "warn" : "good"}`}>{l.seriousness}/10</span>{" "}
                    <span className="muted">{ago(l.at)}</span> — {l.summary}
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="tiny muted">Times shown in {tz.replace("_", " ")}.</p>
        </aside>
      </div>
    </>
  );
}
