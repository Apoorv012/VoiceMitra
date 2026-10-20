"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Room } from "livekit-client";

export type VoiceStatus = "idle" | "joining" | "live" | "error";

function audioHost(): HTMLElement {
  let host = document.getElementById("vm-audio-host");
  if (!host) {
    host = document.createElement("div");
    host.id = "vm-audio-host";
    host.hidden = true;
    document.body.appendChild(host);
  }
  return host;
}

/**
 * One LiveKit room at a time with the microphone on. Used by the doctor, who is first in a private
 * briefing room and then in the patient's room.
 *
 * "Connected" is only reported once the microphone track is confirmed published. Staying joined as a
 * listener whose mic silently failed (blocked permission, no device) looks like a working call to the
 * person but nobody can hear them -- so that case is an error with a message and a retry, never a join.
 */
export function useVoiceRoom() {
  const room = useRef<Room | null>(null);
  const busy = useRef(false);
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<string | null>(null);
  const [needsSoundTap, setNeedsSoundTap] = useState(false);

  const leave = useCallback(() => {
    room.current?.disconnect();
    room.current = null;
    audioHost().replaceChildren();
    setStatus("idle");
    setKind(null);
    setNeedsSoundTap(false);
  }, []);

  const join = useCallback(async (nextKind: string, url: string, token: string) => {
    if (busy.current) return;
    busy.current = true;
    room.current?.disconnect(); // e.g. leaving the briefing room for the patient's
    room.current = null;
    audioHost().replaceChildren();
    setStatus("joining");
    setError(null);
    let r: Room | null = null;
    try {
      const probe = await navigator.mediaDevices.getUserMedia({ audio: true });
      probe.getTracks().forEach((t) => t.stop());
      const { Room, RoomEvent, Track } = await import("livekit-client");
      r = new Room();
      r.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === "audio") audioHost().appendChild(track.attach());
      });
      r.on(RoomEvent.AudioPlaybackStatusChanged, () => setNeedsSoundTap(!r!.canPlaybackAudio));
      await r.connect(url, token);
      try {
        await r.startAudio();
      } catch {
        setNeedsSoundTap(true);
      }
      await r.localParticipant.setMicrophoneEnabled(true);
      if (!r.localParticipant.getTrackPublication(Track.Source.Microphone)?.track) {
        throw new Error("the microphone was not published to the call");
      }
      room.current = r;
      setKind(nextKind);
      setStatus("live");
    } catch (err) {
      r?.disconnect();
      console.error("voice join failed", err);
      const denied = err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "SecurityError");
      setError(denied ? "The microphone is blocked. Allow it for this site in the browser, then try again."
        : `Could not start voice (${err instanceof Error ? err.message : String(err)}).`);
      setStatus("error");
    } finally {
      busy.current = false;
    }
  }, []);

  const enableSound = useCallback(() => {
    void room.current?.startAudio().then(() => setNeedsSoundTap(false)).catch(() => {});
  }, []);

  useEffect(() => () => { room.current?.disconnect(); }, []);

  return { status, error, kind, needsSoundTap, join, leave, enableSound };
}
