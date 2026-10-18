import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** RM 12,300 — negatives in parentheses: (RM 4,200). */
export function rm(value: number): string {
  const abs = Math.abs(Math.round(value)).toLocaleString("en-MY");
  return value < 0 ? `(RM ${abs})` : `RM ${abs}`;
}
