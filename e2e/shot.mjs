import { chromium } from "@playwright/test";
const out = process.argv[2];
const b = await chromium.launch();
for (const [name, theme, w, h] of [["light","light",1280,720],["dark","dark",1280,720],["mobile","light",375,740]]) {
  const ctx = await b.newContext({ viewport: { width: w, height: h } });
  await ctx.addInitScript((t) => localStorage.setItem("helm-theme", t), theme);
  const p = await ctx.newPage();
  const errs = [];
  p.on("console", m => m.type()==="error" && errs.push(m.text()));
  await p.goto("http://localhost:3100/");
  await p.screenshot({ path: `${out}/${name}.png` });
  const overflow = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  console.log(name, "console errors:", errs.length, "h-overflow:", overflow);
}
await b.close();
