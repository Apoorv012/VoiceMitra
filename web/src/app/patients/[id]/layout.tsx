"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { CallProvider } from "@/components/call/CallProvider";
import { CallSheet } from "@/components/call/CallSheet";
import { Icon, type IconName } from "@/components/Icon";
import { LangSwitch } from "@/components/LangSwitch";
import { setIdentity } from "@/lib/identity";
import { useT, type MessageKey } from "@/lib/i18n";

const TABS: { href: string; icon: IconName; label: MessageKey }[] = [
  { href: "", icon: "home", label: "tab_today" },
  { href: "/medicines", icon: "pill", label: "tab_medicines" },
  { href: "/history", icon: "history", label: "tab_history" },
  { href: "/me", icon: "user", label: "tab_me" },
];

export default function PatientLayout({ children }: { children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const pathname = usePathname();
  const { t } = useT();
  const base = `/patients/${id}`;

  // Opening a patient's link on a device remembers them, so the installed app opens straight here.
  // Staff open this app with ?preview=1 to look at (or run a call as) a patient without that
  // overwriting who they are on this browser.
  useEffect(() => {
    if (!new URLSearchParams(window.location.search).has("preview")) setIdentity({ role: "patient", id });
  }, [id]);

  return (
    <CallProvider patientId={id}>
      <div className="phone patient-app">
        <header className="p-head">
          <span className="row" style={{ gap: 10 }}>
            <span className="brand-mark" style={{ width: 34, height: 34, borderRadius: 10 }}><Icon name="mic" /></span>
            <strong>VoiceMitra</strong>
          </span>
          <LangSwitch />
        </header>
        <main className="p-main">{children}</main>
        <nav className="tabbar" aria-label="Main">
          <div className="tabbar-inner">
            {TABS.map((tab) => {
              const href = base + tab.href;
              const on = tab.href === "" ? pathname === base : pathname.startsWith(href);
              return (
                <Link key={tab.label} href={href} className={on ? "on" : ""} aria-current={on ? "page" : undefined}>
                  <Icon name={tab.icon} />
                  {t(tab.label)}
                </Link>
              );
            })}
          </div>
        </nav>
      </div>
      <CallSheet />
    </CallProvider>
  );
}
