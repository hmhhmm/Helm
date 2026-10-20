"use client";

import { useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useEffect, useState } from "react";
import { useT } from "@/i18n";
import { API_URL } from "@/lib/api";
import { LOGIN_EVENT, setToken } from "@/lib/auth";
import { Button } from "./ui/button";
import { Sheet } from "./ui/sheet";
import { useToast } from "./ui/toast";

/** Opens when the server refuses a state changing call. In the public demo the passcode is shown on purpose. */
export function LoginDialog() {
  const { t } = useT();
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [pass, setPass] = useState("");
  const [hint, setHint] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const on = () => {
      setOpen(true);
      fetch(`${API_URL}/auth/config`).then((r) => r.json()).then((j) => setHint(j.demo_hint ?? null)).catch(() => {});
    };
    window.addEventListener(LOGIN_EVENT, on);
    return () => window.removeEventListener(LOGIN_EVENT, on);
  }, []);

  async function submit(code: string) {
    setBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${API_URL}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ passcode: code }) });
      const j = await r.json();
      if (!r.ok) throw new Error(typeof j.detail === "string" ? j.detail : "Login failed");
      setToken(j.token);
      setOpen(false);
      setPass("");
      await qc.invalidateQueries();
      toast({ title: t("login.done"), tone: "ok" });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={setOpen} title={t("login.title")} description={t("login.sub")} side="center">
      <form onSubmit={(e) => { e.preventDefault(); submit(pass); }} className="space-y-3" data-testid="login-form">
        <label className="block text-sm font-medium" htmlFor="passcode">{t("login.passcode")}</label>
        <div className="flex min-h-11 items-center gap-2 rounded-lg border border-border bg-surface px-3 focus-within:outline focus-within:outline-2 focus-within:outline-accent">
          <Lock aria-hidden className="size-4 text-muted" />
          <input id="passcode" type="password" autoComplete="current-password" value={pass} onChange={(e) => setPass(e.target.value)} className="w-full bg-transparent py-2 outline-none" />
        </div>
        {err && <p role="alert" className="text-sm text-deny">{err}</p>}
        <Button type="submit" disabled={busy || !pass} className="w-full" data-testid="login-submit">{t("login.go")}</Button>
        {hint && (
          <div className="rounded-lg bg-subtle p-3 text-[13px] text-muted">
            {t("login.demo", { code: hint })}
            <Button type="button" variant="secondary" size="sm" className="mt-2 w-full" disabled={busy} onClick={() => submit(hint)} data-testid="login-demo">{t("login.useDemo")}</Button>
          </div>
        )}
      </form>
    </Sheet>
  );
}
