import type { Lang } from "@/i18n";

/** RM 12,300; negatives in parentheses: (RM 4,200). */
export function rm(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const abs = Math.abs(Math.round(value)).toLocaleString("en-MY");
  return value < 0 ? `(RM ${abs})` : `RM ${abs}`;
}

export function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

const MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MONTHS_MS = ["Jan", "Feb", "Mac", "Apr", "Mei", "Jun", "Jul", "Ogos", "Sep", "Okt", "Nov", "Dis"];
const DAYS_EN = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAYS_MS = ["Ahd", "Isn", "Sel", "Rab", "Kha", "Jum", "Sab"];

export function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

/** 24 Nov */
export function fdate(iso: string | null | undefined, lang: Lang = "en"): string {
  if (!iso) return "—";
  const d = parseDate(iso);
  return `${d.getUTCDate()} ${(lang === "ms" ? MONTHS_MS : MONTHS_EN)[d.getUTCMonth()]}`;
}

/** Mon 19 Oct 2026 */
export function flong(iso: string, lang: Lang = "en"): string {
  const d = parseDate(iso);
  return `${(lang === "ms" ? DAYS_MS : DAYS_EN)[d.getUTCDay()]} ${fdate(iso, lang)} ${d.getUTCFullYear()}`;
}

export function addDays(iso: string, n: number): string {
  const d = parseDate(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((parseDate(b).getTime() - parseDate(a).getTime()) / 86_400_000);
}

/** "2026-09" -> "Sep" */
export function fmonth(ym: string, lang: Lang = "en"): string {
  const m = Number(ym.split("-")[1]);
  return (lang === "ms" ? MONTHS_MS : MONTHS_EN)[m - 1];
}
