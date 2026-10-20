"use client";

import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { useT, type MessageKey } from "@/lib/i18n";
import { initials } from "@/lib/format";
import { useCall, type Phase } from "./CallProvider";

const STATUS: Partial<Record<Phase, MessageKey>> = {
  starting: "call_connecting",
  connecting: "call_connecting",
  live: "call_live",
  hold: "call_hold",
  briefing: "call_briefing",
  merged: "call_merged",
  ended: "call_ended",
};

/** The call itself: full screen on a phone, a floating panel on a desktop. */
export function CallSheet() {
  const call = useCall();
  const { t } = useT();
  const [text, setText] = useState("");
  const log = useRef<HTMLDivElement>(null);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [call.lines.length]);

  if (!call.open || call.phase === "idle") return null;

  const live = call.phase === "live" || call.phase === "merged";
  const doctor = call.phase === "merged" && call.doctorName;
  const waiting = call.phase === "hold" || call.phase === "briefing";
  const typing = call.kind === "chat" && (call.phase === "live" || call.phase === "merged");
  const status =
    call.phase === "error"
      ? call.error
      : t(STATUS[call.phase] ?? "call_connecting", { name: call.doctorName || "Doctor" });

  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={t("talk_title")}>
      <div className="sheet-head">
        <span className={live ? "pulse" : waiting ? "pulse warm" : ""}>
          <span className="avatar" aria-hidden="true">{doctor ? initials(call.doctorName) : <Icon name="mic" />}</span>
        </span>
        <strong style={{ fontSize: "1.25rem" }}>{doctor ? call.doctorName : "VoiceMitra"}</strong>
        <p className="sheet-status" role="status" aria-live="polite">{status}</p>
      </div>

      <div className="sheet-log" ref={log}>
        <div className="chat">
          {call.lines.map((l) => (
            <div key={l.id} className={`bubble ${l.who === "me" ? "me" : l.who === "doctor" ? "doctor" : l.who === "note" ? "note" : ""}`}>
              {l.who === "doctor" && <div className="who">{call.doctorName || "Doctor"}</div>}
              {l.text}
            </div>
          ))}
        </div>
      </div>

      <div className="sheet-foot">
        {call.needsSoundTap && call.phase !== "ended" && (
          <button type="button" className="btn secondary block" onClick={call.enableSound}>
            <Icon name="sound" />Tap to hear VoiceMitra
          </button>
        )}
        {typing && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              call.sendText(text);
              setText("");
            }}
          >
            <input type="text" value={text} onChange={(e) => setText(e.target.value)} placeholder={t("type_reply")} maxLength={2000} autoComplete="off" />
            <button type="submit" className="btn" aria-label={t("send")}><Icon name="send" /></button>
          </form>
        )}
        {call.phase === "ended" || call.phase === "error" ? (
          <button type="button" className="btn secondary block xl" onClick={call.close}>{t("close")}</button>
        ) : (
          <button type="button" className="btn danger block xl" onClick={() => void call.end()}>
            <Icon name="phone-off" />{t("end_call")}
          </button>
        )}
      </div>
    </div>
  );
}
