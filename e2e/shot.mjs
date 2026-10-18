import { chromium } from "@playwright/test";
const out = process.argv[2];
const base = process.env.BASE ?? "http://localhost:3000";
const pages = (process.argv[3] ?? "/,/forecast,/payments,/collections,/cash,/policy,/agents").split(",");
const sizes = (process.argv[4] ?? "desktop").split(",");
const themes = (process.argv[5] ?? "light").split(",");
const b = await chromium.launch();
for (const size of sizes) for (const theme of themes) {
  const [w, h] = size === "mobile" ? [375, 760] : [1280, 800];
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  await ctx.addInitScript((t) => localStorage.setItem("helm-theme", t), theme);
  const p = await ctx.newPage();
  const errs = [];
  p.on("console", (m) => m.type() === "error" && errs.push(m.text()));
  p.on("pageerror", (e) => errs.push("pageerror " + e.message));
  for (const path of pages) {
    await p.goto(base + path, { waitUntil: "networkidle" });
    await p.waitForTimeout(700);
    const name = `${out}/${(path === "/" ? "today" : path.slice(1).replace(/[\/?=&]/g, "_"))}-${size}-${theme}.png`;
    const full = await p.evaluate(() => document.documentElement.scrollHeight);
    await p.setViewportSize({ width: w, height: Math.min(full, 4000) });
    await p.waitForTimeout(1300);
    await p.screenshot({ path: name });
    await p.setViewportSize({ width: w, height: h });
    const overflow = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    console.log(path, size, theme, "overflowX:", overflow);
  }
  console.log(size, theme, "console errors:", errs.length, errs.slice(0, 4));
  await ctx.close();
}
await b.close();
