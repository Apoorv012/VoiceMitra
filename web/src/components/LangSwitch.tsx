"use client";

import { setLang, useT } from "@/lib/i18n";

export function LangSwitch() {
  const { lang } = useT();
  return (
    <div className="lang-switch" role="group" aria-label="Language">
      <button type="button" className={lang === "en" ? "on" : ""} onClick={() => setLang("en")} aria-pressed={lang === "en"}>
        EN
      </button>
      <button type="button" className={lang === "hi" ? "on" : ""} onClick={() => setLang("hi")} aria-pressed={lang === "hi"}>
        हिं
      </button>
    </div>
  );
}
