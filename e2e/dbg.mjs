import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
await p.goto("http://localhost:3000/forecast", { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
const info = await p.evaluate(() => {
  const area = document.querySelector("path.recharts-area-area");
  const cs = getComputedStyle(area);
  const g = area.closest("g");
  const clips = [...document.querySelectorAll("clipPath rect")].map((r) => [r.getAttribute("x"), r.getAttribute("y"), r.getAttribute("width"), r.getAttribute("height")]);
  const line = document.querySelector("path.recharts-line-curve");
  return { areaDisplay: cs.display, vis: cs.visibility, clips, lineStroke: line.getAttribute("stroke"), lineDash: line.getAttribute("stroke-dasharray"), lineStyle: line.getAttribute("style"), areaStyle: area.getAttribute("style"), gClip: g.getAttribute("clip-path") };
});
console.log(JSON.stringify(info, null, 1));
await b.close();
