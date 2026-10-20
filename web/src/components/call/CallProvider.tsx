"use client";

// The patient's call, for the whole patient app. It lives in the layout (not on a page) so a call keeps
// going if the patient switches tabs. One provider handles both kinds of call the backend can start:
//   voice -- a LiveKit room (the agent speaks; the patient's mic is published), with a live transcript
//   chat  -- typed messages over the same socket (used when an operator starts a text call)
// Events come from the backend's patient socket; nothing is polled.

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { Room } from "livekit-client";
import { api, ApiError } from "@/lib/api";
import type { ChatMessage, LogEntry, PatientEvent } from "@/lib/events";
import { translate, useT } from "@/lib/i18n";
import { useSocket } from "@/lib/ws";

export type Phase = "idle" | "starting" | "connecting" | "live" | "hold" | "briefing" | "merged" | "ended" | "error";
export type Line = { id: number; who: "agent" | "me" | "doctor" | "note"; text: string };

type CallApi = {
  open: boolean;
  phase: Phase;
  kind: "voice" | "chat" | null;
  lines: Line[];
  doctorName: string;
  error: string | null;
  needsSoundTap: boolean;
  inCall: boolean;
  start: () => Promise<void>;
  end: () => Promise<void>;
  close: () => void;
  reopen: () => void;
  sendText: (text: string) => void;
  enableSound: () => void;
};

const Ctx = createContext<CallApi | null>(null);

export function useCall(): CallApi {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCall must be used inside <CallProvider>");
  return ctx;
}

const ACTIVE: Phase[] = ["starting", "connecting", "live", "hold", "briefing", "merged"];

export function CallProvider({ patientId, children }: { patientId: string; children: ReactNode }) {
  const { lang } = useT();
  const [open, setOpen] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [kind, setKind] = useState<"voice" | "chat" | null>(null);
  const [lines, setLines] = useState<Line[]>([]);
  const [doctorName, setDoctorName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needsSoundTap, setNeedsSoundTap] = useState(false);

  const room = useRef<Room | null>(null);
  const joining = useRef(false);
  const audioHost = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);
  const callId = useRef<string | null>(null);
  const shownIndex = useRef(0);
  const escalated = useRef(false);
  const langRef = useRef(lang);
  const phaseRef = useRef<Phase>("idle");
  const send = useRef<(data: unknown) => boolean>(() => false);

  useEffect(() => {
    langRef.current = lang;
  });

  const setPhaseBoth = useCallback((p: Phase) => {
    phaseRef.current = p;
    setPhase(p);
  }, []);

  const addLine = useCallback((who: Line["who"], text: string) => {
    if (!text) return;
    setLines((prev) => [...prev, { id: nextId.current++, who, text }]);
  }, []);

  const resetFor = useCallback((id: string | null, k: "voice" | "chat") => {
    callId.current = id;
    shownIndex.current = 0;
    escalated.current = false;
    nextId.current = 1;
    setLines([]);
    setDoctorName("");
    setError(null);
    setKind(k);
    setOpen(true);
  }, []);

  const leaveRoom = useCallback(() => {
    room.current?.disconnect();
    room.current = null;
    joining.current = false;
    audioHost.current?.replaceChildren();
    setNeedsSoundTap(false);
  }, []);

  // --- voice: join the LiveKit room --------------------------------------------------------------
  const joinVoice = useCallback(async (url: string, token: string) => {
    if (room.current || joining.current) return; // the snapshot and the live event can both arrive
    joining.current = true;
    setPhaseBoth("connecting");
    try {
      // Mic before room: the agent starts speaking the moment the patient joins, so asking for the
      // microphone afterwards would have it greet while the permission prompt is still open.
      const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
      probe.getTracks().forEach((t) => t.stop());
      const { Room, RoomEvent, Track } = await import("livekit-client");
      const r = new Room();
      r.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === "audio") audioHost.current?.appendChild(track.attach());
      });
      r.on(RoomEvent.AudioPlaybackStatusChanged, () => setNeedsSoundTap(!r.canPlaybackAudio));
      r.on(RoomEvent.Disconnected, () => {
        if (room.current === r) {
          room.current = null;
          if (ACTIVE.includes(phaseRef.current)) setPhaseBoth("ended");
        }
      });
      await r.connect(url, token);
      room.current = r;
      try {
        await r.startAudio();
      } catch {
        setNeedsSoundTap(true);
      }
      await r.localParticipant.setMicrophoneEnabled(true);
      if (!r.localParticipant.getTrackPublication(Track.Source.Microphone)?.track) {
        throw new Error("microphone not published");
      }
      if (!escalated.current) setPhaseBoth("live");
    } catch (err) {
      leaveRoom();
      const denied = err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "SecurityError");
      setError(denied ? translate(langRef.current, "mic_blocked")
        : translate(langRef.current, "call_failed", { err: err instanceof Error ? err.message : String(err) }));
      setPhaseBoth("error");
    } finally {
      joining.current = false;
    }
  }, [leaveRoom, setPhaseBoth]);

  // --- events from the backend -------------------------------------------------------------------
  const applyEscalation = useCallback((e: { status?: string; doctor_name?: string | null }) => {
    escalated.current = true;
    if (e.doctor_name) setDoctorName(e.doctor_name);
    setPhaseBoth(e.status === "merged" ? "merged" : e.status === "briefing" ? "briefing" : "hold");
  }, [setPhaseBoth]);

  const addEntry = useCallback((en: LogEntry) => {
    if (en.channel === "doctor_briefing") return; // the doctor's private chat with the agent
    if (en.type === "agent_said") addLine("agent", en.content ?? "");
    else if (en.type === "patient_said") addLine("me", en.content ?? "");
    else if (en.type === "doctor_said") addLine("doctor", en.content ?? "");
    // tool calls and bookkeeping entries are for staff, never the patient
  }, [addLine]);

  // A typed chat message, de-duplicated by its index (a snapshot and live events can overlap).
  const addChatMessage = useCallback((forCall: string, m: ChatMessage) => {
    if (forCall !== callId.current || m.index < shownIndex.current) return;
    shownIndex.current = m.index + 1;
    addLine(m.role === "agent" ? "agent" : m.role === "doctor" ? "doctor" : m.role === "system" ? "note" : "me", m.text);
  }, [addLine]);

  const onEvent = useCallback((e: PatientEvent) => {
    switch (e.type) {
      case "voice_call":
        resetFor(e.call_id, "voice");
        void joinVoice(e.url, e.token);
        return;
      case "log_entry":
        if (e.call_id !== callId.current) resetFor(e.call_id, "voice");
        addEntry(e.entry);
        return;
      case "voice_call_ended":
        leaveRoom();
        if (ACTIVE.includes(phaseRef.current)) setPhaseBoth("ended");
        return;
      case "snapshot":
        if (e.voice) {
          if (callId.current !== e.voice.call_id) {
            resetFor(e.voice.call_id, "voice");
            (e.log ?? []).forEach(addEntry);
          }
          if (e.escalation) applyEscalation(e.escalation);
          void joinVoice(e.voice.url, e.voice.token);
        } else if (e.call_id) {
          if (callId.current !== e.call_id) {
            resetFor(e.call_id, "chat");
            setPhaseBoth("live");
          }
          if (e.escalation) applyEscalation(e.escalation);
          const chatCall = e.call_id;
          (e.messages ?? []).forEach((m) => addChatMessage(chatCall, m));
          if (!e.active) setPhaseBoth("ended");
        }
        // With nothing live, a finished call's transcript stays on screen until it is closed.
        return;
      case "call_started":
        resetFor(e.call_id, "chat");
        setPhaseBoth("live");
        return;
      case "message":
        addChatMessage(e.call_id, e);
        return;
      case "escalation":
        if (kind === "voice" || e.call_id === callId.current || !e.call_id) applyEscalation(e);
        return;
      case "call_ended":
        if (e.call_id === callId.current) setPhaseBoth("ended");
        return;
    }
  }, [addChatMessage, addEntry, applyEscalation, joinVoice, kind, leaveRoom, resetFor, setPhaseBoth]);

  const socket = useSocket<PatientEvent>(`/ws/patients/${patientId}/chat`, onEvent);
  useEffect(() => {
    send.current = socket.send;
  });

  useEffect(() => () => leaveRoom(), [leaveRoom]);

  // --- what the screens can do -------------------------------------------------------------------
  const start = useCallback(async () => {
    resetFor(null, "voice");
    setPhaseBoth("starting");
    try {
      await api(`/api/patients/${patientId}/voice-call`, { method: "POST" });
      // The backend now publishes `voice_call`; joining happens from that event.
    } catch (err) {
      setError(err instanceof ApiError ? err.message : translate(langRef.current, "talk_error"));
      setPhaseBoth("error");
    }
  }, [patientId, resetFor, setPhaseBoth]);

  const end = useCallback(async () => {
    try {
      await api(`/api/patients/${patientId}/call/end`, { method: "POST" });
    } catch {
      /* the socket reports the end; if the request failed the call is still live */
    }
  }, [patientId]);

  const value: CallApi = {
    open, phase, kind, lines, doctorName, error, needsSoundTap,
    inCall: ACTIVE.includes(phase),
    start, end,
    close: () => {
      setOpen(false);
      if (!ACTIVE.includes(phaseRef.current)) {
        setPhaseBoth("idle");
        setLines([]);
      }
    },
    reopen: () => setOpen(true),
    sendText: (text) => {
      if (text.trim()) send.current({ type: "reply", text: text.trim() });
    },
    enableSound: () => {
      void room.current?.startAudio().then(() => setNeedsSoundTap(false)).catch(() => {});
    },
  };

  return (
    <Ctx.Provider value={value}>
      {children}
      <div ref={audioHost} hidden aria-hidden="true" />
    </Ctx.Provider>
  );
}
