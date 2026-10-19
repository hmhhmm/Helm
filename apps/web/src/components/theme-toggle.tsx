"use client";

import { Moon, Sun } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useT } from "@/i18n";

type Theme = "light" | "dark";

export function useTheme() {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("helm-theme");
    } catch {}
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved === "dark" || saved === "light") setTheme(saved);
    else if (window.matchMedia("(prefers-color-scheme: dark)").matches) setTheme("dark");
  }, []);
  const toggle = useCallback(() => {
    const cur = document.documentElement.dataset.theme === "dark" ? "dark" : "light";
    const next: Theme = cur === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("helm-theme", next);
    } catch {}
  }, []);
  return { theme, toggle };
}

export function ThemeToggle() {
  const { t } = useT();
  const { theme, toggle } = useTheme();
  return (
    <button
      onClick={toggle}
      aria-label={t("theme.toggle")}
      className="inline-flex size-11 cursor-pointer items-center justify-center rounded-lg border border-border bg-surface text-muted hover:bg-subtle md:size-9"
    >
      {theme === "light" ? <Moon aria-hidden className="size-4" /> : <Sun aria-hidden className="size-4" />}
    </button>
  );
}
