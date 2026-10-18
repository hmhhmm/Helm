"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { en } from "@/i18n/en";

type Theme = "light" | "dark";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");

  useEffect(() => {
    let saved: string | null = null;
    try {
      saved = localStorage.getItem("helm-theme");
    } catch {}
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (saved === "dark") setTheme("dark");
  }, []);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("helm-theme", next);
    } catch {}
  }

  return (
    <button
      onClick={toggle}
      aria-label={en.theme.toggle}
      className="inline-flex size-11 items-center justify-center rounded-lg border border-border bg-surface text-text hover:bg-bg"
    >
      {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </button>
  );
}
