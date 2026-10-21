"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { Avatar } from "@/components/ui";
import { clearIdentity } from "@/lib/identity";

export type NavItem = { href: string; label: string; icon: IconName; match?: (path: string) => boolean };

/** Chrome for the doctor and operator screens: brand, navigation, who's signed in, and a way to switch. */
export function StaffShell({
  nav, name, role, children,
}: { nav: NavItem[]; name: string; role: string; children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  return (
    <>
      <header className="s-head">
        <div className="s-head-inner">
          <Link href={nav[0].href} className="s-brand">
            <span className="brand-mark" style={{ width: 36, height: 36, borderRadius: 12 }}><Icon name="mic" /></span>
            <span translate="no">VoiceMitra</span>
          </Link>
          <nav className="s-nav" aria-label="Main">
            {nav.map((n) => {
              const on = n.match ? n.match(pathname) : pathname === n.href;
              return (
                <Link key={n.href} href={n.href} className={on ? "on" : ""} aria-current={on ? "page" : undefined}>
                  {n.label}
                </Link>
              );
            })}
          </nav>
          <div className="s-who">
            <Avatar name={name} size="sm" />
            <span className="hide-sm">
              <strong>{name}</strong>
              <span className="muted"> · {role}</span>
            </span>
            <button
              type="button"
              className="btn ghost sm"
              aria-label="Switch user"
              onClick={() => {
                clearIdentity();
                router.push("/");
              }}
            >
              <Icon name="logout" />
            </button>
          </div>
        </div>
      </header>
      <main className="s-main">{children}</main>
    </>
  );
}
