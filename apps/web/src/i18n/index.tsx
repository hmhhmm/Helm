"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { dict, type Key } from "./dict";

export type Lang = "en" | "ms";
export type { Key };

interface Ctx {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: Key, params?: Record<string, string | number>) => string;
  /** Pick the right language from a {en, ms} pair the API sends. */
  txt: (x: { en: string; ms: string }) => string;
}

const I18n = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("helm-lang");
    } catch {}
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved === "ms") setLangState("ms");
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang === "ms" ? "ms" : "en";
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem("helm-lang", l);
    } catch {}
  }, []);

  const value = useMemo<Ctx>(
    () => ({
      lang,
      setLang,
      t: (key, params) => {
        let s: string = dict[lang][key] ?? dict.en[key] ?? key;
        if (params) for (const [k, v] of Object.entries(params)) s = s.replaceAll(`{${k}}`, String(v));
        return s;
      },
      txt: (x) => (lang === "ms" ? x.ms || x.en : x.en),
    }),
    [lang, setLang],
  );
  return <I18n.Provider value={value}>{children}</I18n.Provider>;
}

export function useT(): Ctx {
  const c = useContext(I18n);
  if (!c) throw new Error("useT must be used inside I18nProvider");
  return c;
}
