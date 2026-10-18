import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { resetDemo } from "./helpers";

const PAGES = ["/", "/forecast", "/payments", "/collections", "/cash", "/policy", "/agents"];

test.beforeAll(async ({ request }) => { await request.post("http://localhost:8000/sim/reset"); });

for (const theme of ["light", "dark"] as const) {
  for (const path of PAGES) {
    test(`a11y ${theme} ${path}: no serious violations, no console errors`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
      page.on("pageerror", (e) => errors.push(e.message));
      await page.addInitScript((t) => localStorage.setItem("helm-theme", t), theme);
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(500);
      const res = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
      const bad = res.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
      expect(errors).toEqual([]);
    });
  }
}

test.describe("phone width (375px)", () => {
  test.use({ viewport: { width: 375, height: 740 } });
  for (const path of PAGES) {
    test(`no horizontal scroll and 44px targets on ${path}`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(400);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(overflow).toBeLessThanOrEqual(1);
      const small = await page.evaluate(() => {
        const out: string[] = [];
        for (const el of document.querySelectorAll<HTMLElement>("button, a[href], [role=button], [role=tab], input[type=checkbox], select, [role=switch]")) {
          const lab = el.closest("label");
          const r = (lab ?? el).getBoundingClientRect(); // a checkbox inside a 44px label is a 44px target
          if (r.width < 3 || r.height < 3) continue; // sr-only skip link
          if (r.height < 43.5 && getComputedStyle(el).display !== "inline") out.push(`${el.tagName} "${(el.textContent || el.getAttribute("aria-label") || "").trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`);
        }
        return out;
      });
      expect(small).toEqual([]);
    });
  }

  test("approval page works on a phone", async ({ page, request }) => {
    await resetDemo(page);
    const r = await (await request.post("http://localhost:8000/sim/malicious-invoice")).json();
    await page.goto(`/approve/${r.data.proposal_id}`);
    await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
    await page.getByRole("button", { name: "Hold" }).click();
    await expect(page.getByText("No money moved").first()).toBeVisible();
  });
});
