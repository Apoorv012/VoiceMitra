"use client";

// "Connect a phone": shows a 6-digit code the VoiceMitra phone app pairs with (mobile/API.md).
// While the code is on screen the list of paired phones is re-read every few seconds, so the card
// says "Phone connected" as soon as the phone has used it.

import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { api, useApi } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { DeviceView, PairingCode } from "@/lib/types";

type State =
  | { step: "idle" }
  | { step: "loading" }
  | { step: "code"; code: string; deadline: number; knownIds: string[] }
  | { step: "error" };

function mmss(seconds: number) {
  const s = Math.max(0, Math.ceil(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function ConnectPhone({ patientId }: { patientId: string }) {
  const { t } = useT();
  const [state, setState] = useState<State>({ step: "idle" });
  const [now, setNow] = useState(() => Date.now());
  // Re-read the phone list every 3 s while a live code is on screen and no new phone has shown up.
  // Memoised: SWR restarts its timer whenever this function changes, and the countdown re-renders every second.
  const pollEvery = useCallback(
    (latest?: DeviceView[]) =>
      state.step === "code" && Date.now() < state.deadline && !latest?.some((d) => !state.knownIds.includes(d.id))
        ? 3000
        : 0,
    [state],
  );
  const devices = useApi<DeviceView[]>(`/api/patients/${patientId}/devices`, 0, { refreshInterval: pollEvery });
  const list = devices.data ?? [];

  // A phone we hadn't seen before has paired: the code did its job.
  const added = state.step === "code" ? list.find((d) => !state.knownIds.includes(d.id)) : undefined;
  const left = state.step === "code" ? (state.deadline - now) / 1000 : 0;
  const expired = state.step === "code" && !added && left <= 0;
  const waiting = state.step === "code" && !added && !expired;

  // Tick the countdown while a code is on screen.
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  async function getCode() {
    setState({ step: "loading" });
    try {
      const res = await api<PairingCode>(`/api/patients/${patientId}/pairing-code`, { method: "POST" });
      const started = Date.now();
      setNow(started);
      setState({ step: "code", code: res.code, deadline: started + res.expires_in * 1000, knownIds: list.map((d) => d.id) });
    } catch {
      setState({ step: "error" });
    }
  }

  return (
    <section className="card" aria-labelledby="connect-phone-title">
      <div className="row top">
        <Icon name="phone" className="lg" />
        <div className="grow">
          <h2 id="connect-phone-title">{t("phone_title")}</h2>
          <p className="small ink-2" style={{ margin: "4px 0 12px" }}>{t("phone_sub")}</p>

          {state.step === "code" && waiting && (
            <div className="pair-box">
              <p className="small">{t("phone_enter")}</p>
              {/* Read out digit by digit by screen readers; grouped 3 + 3 on screen. */}
              <p className="pair-code" translate="no" aria-label={state.code.split("").join(" ")}>
                {state.code.slice(0, 3)}&nbsp;{state.code.slice(3)}
              </p>
              <p className="small muted" role="timer" aria-live="off">{t("phone_expires", { time: mmss(left) })}</p>
              <p className="small muted" role="status" aria-live="polite">{t("phone_waiting")}</p>
            </div>
          )}

          {expired && (
            <div className="callout warn" role="status" style={{ marginBottom: 12 }}>
              <Icon name="clock" /><p>{t("phone_expired")}</p>
            </div>
          )}

          {added && (
            <div className="callout good" role="status" style={{ marginBottom: 12 }}>
              <Icon name="check" /><p><strong>{t("phone_done")}</strong>{added.name ? ` · ${added.name}` : ""}</p>
            </div>
          )}

          {state.step === "error" && (
            <div className="callout crit" role="alert" style={{ marginBottom: 12 }}>
              <Icon name="alert" /><p>{t("phone_error")}</p>
            </div>
          )}

          {!waiting && (
            <button type="button" className="btn" disabled={state.step === "loading"} onClick={() => void getCode()}>
              {expired ? t("phone_new_code") : list.length ? t("phone_another") : t("phone_btn")}
            </button>
          )}

          {list.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <p className="small muted">{t("phone_connected")}</p>
              <ul className="small" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {list.map((d) => (
                  <li key={d.id}>{d.name || t("phone_unnamed")} <span className="muted">({d.platform === "ios" ? "iPhone" : "Android"})</span></li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
