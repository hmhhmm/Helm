import { chromium } from "@playwright/test";
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
await p.goto("http://localhost:3000/forecast", { waitUntil: "networkidle" });
for (const ms of [300, 1200, 3000]) {
  await p.waitForTimeout(ms);
  const box = await p.locator("svg.recharts-surface").first().boundingBox();
  await p.screenshot({ path: `/private/tmp/claude-501/-Users-hiapmeng-Downloads-Helm-Helm/fd1191a0-04da-4593-b66d-95789a9ebae7/scratchpad/chart-${ms}.png`, clip: { x: box.x, y: box.y, width: box.width, height: box.height } });
}
await b.close();
