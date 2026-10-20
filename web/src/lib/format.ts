import { translate, type Lang } from "./i18n";

// Dates and times arrive as ISO strings; "today" and the dose times are decided by the server in its
// timezone (`timezone` on every view), so everything is rendered in that zone, not the device's.

const locale = (lang: Lang) => (lang === "hi" ? "hi-IN" : "en-IN");

/** "9:00 PM" */
export function timeOf(iso: string, tz: string): string {
  return new Intl.DateTimeFormat("en-IN", { timeZone: tz, hour: "numeric", minute: "2-digit", hour12: true })
    .format(new Date(iso))
    .toUpperCase();
}

/** "21:00" -> "9:00 PM" (a stored dose time, which has no date or zone). */
export function clockLabel(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  if (Number.isNaN(h)) return hhmm;
  return `${h % 12 || 12}:${String(m || 0).padStart(2, "0")} ${h < 12 ? "AM" : "PM"}`;
}

/** "2026-10-21" in the given zone, to compare calendar days. */
function dayKey(date: Date, tz: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(date);
}

/** "Today", "Yesterday", or "Tue, 14 Oct". */
export function dayLabel(iso: string, tz: string, lang: Lang = "en"): string {
  const date = new Date(iso);
  const today = dayKey(new Date(), tz);
  if (dayKey(date, tz) === today) return translate(lang, "today");
  if (dayKey(date, tz) === dayKey(new Date(Date.now() - 86_400_000), tz)) return translate(lang, "yesterday");
  return new Intl.DateTimeFormat(locale(lang), { timeZone: tz, weekday: "short", day: "numeric", month: "short" }).format(date);
}

/** "Today, 9:41 AM" */
export function when(iso: string, tz: string, lang: Lang = "en"): string {
  return `${dayLabel(iso, tz, lang)}, ${timeOf(iso, tz)}`;
}

/** "14 Oct" */
export function dateShort(iso: string, tz: string, lang: Lang = "en"): string {
  return new Intl.DateTimeFormat(locale(lang), { timeZone: tz, day: "numeric", month: "short" }).format(new Date(iso));
}

/** "14 Oct" for a plain "YYYY-MM-DD" date (no time, no zone involved). */
export function dayOfDate(date: string, lang: Lang = "en"): string {
  return new Intl.DateTimeFormat(locale(lang), { timeZone: "UTC", day: "numeric", month: "short" }).format(new Date(`${date}T12:00:00Z`));
}

/** Short weekday of a plain "YYYY-MM-DD" date: "Tue" / "मंगल". */
export function weekdayOf(date: string, lang: Lang = "en"): string {
  return new Intl.DateTimeFormat(locale(lang), { timeZone: "UTC", weekday: "short" }).format(new Date(`${date}T12:00:00Z`));
}

/** "Wednesday, 21 October" for today. */
export function fullDateToday(tz: string, lang: Lang = "en"): string {
  return new Intl.DateTimeFormat(locale(lang), { timeZone: tz, weekday: "long", day: "numeric", month: "long" }).format(new Date());
}

export function isToday(date: string, tz: string): boolean {
  return date === dayKey(new Date(), tz);
}

/** "in 35 min", "in 2 h", "now" */
export function inWords(iso: string, lang: Lang = "en"): string {
  const seconds = Math.round((new Date(iso).getTime() - Date.now()) / 1000);
  if (seconds <= 60) return translate(lang, "now");
  if (seconds < 3600) return translate(lang, "in_min", { n: Math.floor(seconds / 60) });
  return translate(lang, "in_hours", { n: Math.round(seconds / 3600) });
}

/** English "5 min ago" for staff screens. */
export function ago(iso: string): string {
  const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86_400) return `${Math.floor(seconds / 3600)} h ago`;
  const days = Math.floor(seconds / 86_400);
  return days === 1 ? "yesterday" : `${days} days ago`;
}

export function initials(name: string): string {
  const parts = name.replace(/\./g, " ").split(/\s+/).filter((p) => p && !/^(dr|mr|mrs|ms)$/i.test(p));
  return parts.slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "?";
}

export function greetingKey(tz: string): "good_morning" | "good_afternoon" | "good_evening" {
  const hour = Number(new Intl.DateTimeFormat("en-GB", { timeZone: tz, hour: "2-digit", hour12: false }).format(new Date()));
  // Late night (before 4) counts as the evening that never ended, not "morning".
  return hour >= 4 && hour < 12 ? "good_morning" : hour >= 12 && hour < 17 ? "good_afternoon" : "good_evening";
}
