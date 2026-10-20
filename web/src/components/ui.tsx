"use client";

import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";
import { initials } from "@/lib/format";
import { useT, type MessageKey } from "@/lib/i18n";
import type { AttentionLevel, DayState, SlotState } from "@/lib/types";

// One look for every dose state on every screen: colour + icon + word. Colour never carries it alone.
const SLOT: Record<SlotState, { tone: string; icon: IconName; label: MessageKey }> = {
  taken: { tone: "good", icon: "check", label: "dose_taken" },
  partial: { tone: "warn", icon: "alert", label: "dose_partial" },
  missed: { tone: "crit", icon: "x", label: "dose_missed" },
  later: { tone: "accent", icon: "clock", label: "dose_later" },
  unknown: { tone: "", icon: "help", label: "dose_unknown" },
  skipped: { tone: "", icon: "shield", label: "dose_skipped" },
  upcoming: { tone: "", icon: "clock", label: "dose_upcoming" },
  due: { tone: "warn", icon: "clock", label: "dose_due" },
  no_checkin: { tone: "", icon: "help", label: "dose_nocheckin" },
};

export function SlotChip({ state, large = false }: { state: string; large?: boolean }) {
  const { t } = useT();
  const m = SLOT[state as SlotState] ?? SLOT.no_checkin;
  return (
    <span className={`chip ${m.tone} ${large ? "lg" : ""}`}>
      <Icon name={m.icon} />
      {t(m.label)}
    </span>
  );
}

const DAY_ICON: Record<DayState, IconName | null> = {
  good: "check", mixed: "alert", missed: "x", unknown: "help", upcoming: null, none: null,
};

/** The round marker for a whole day in the week strip. */
export function DayDot({ state }: { state: string }) {
  const icon = DAY_ICON[state as DayState] ?? null;
  return <span className={`dot ${state}`}>{icon && <Icon name={icon} />}</span>;
}

/** Staff-side: should a doctor look at this patient? */
export function AttentionChip({ level }: { level: string }) {
  const l = level as AttentionLevel;
  if (l === "critical") return <span className="chip crit"><Icon name="alert" />Needs attention</span>;
  if (l === "warning") return <span className="chip warn"><Icon name="alert" />Worth a look</span>;
  return <span className="chip good"><Icon name="check" />Stable</span>;
}

export function Avatar({ name, tone = "", size = "" }: { name: string; tone?: string; size?: string }) {
  return <span className={`avatar ${size} ${tone}`} aria-hidden="true">{initials(name)}</span>;
}

export function Loading() {
  const { t } = useT();
  return <div className="empty" role="status">{t("loading")}</div>;
}

export function ErrorState({ onRetry }: { onRetry?: () => void }) {
  const { t } = useT();
  return (
    <div className="empty" role="alert">
      <Icon name="alert" />
      <p>{t("load_error")}</p>
      {onRetry && <button className="btn secondary sm" style={{ marginTop: 12 }} onClick={onRetry}>{t("retry")}</button>}
    </div>
  );
}

export function Empty({ icon, children }: { icon: IconName; children: ReactNode }) {
  return (
    <div className="empty">
      <Icon name={icon} />
      <p>{children}</p>
    </div>
  );
}

/** Legend for the day dots, so the week strip is readable without guessing. */
export function WeekLegend() {
  const { t } = useT();
  const items: [DayState, MessageKey][] = [
    ["good", "day_good"], ["mixed", "day_mixed"], ["missed", "day_missed"], ["unknown", "day_unknown"],
  ];
  return (
    <div className="legend">
      {items.map(([s, k]) => (
        <span key={s}><DayDot state={s} />{t(k)}</span>
      ))}
    </div>
  );
}
