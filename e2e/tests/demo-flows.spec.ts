import { expect, test } from "@playwright/test";
import { API, openSimulator, resetDemo } from "./helpers";

test.describe.configure({ mode: "serial" });

test.beforeEach(async ({ page }) => { await resetDemo(page); });

test("the 60-second story: today -> forecast -> payments -> decision trace", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Synthetic demo data").first()).toBeVisible();
  await expect(page.getByText("Demo bank").first()).toBeVisible();
  await expect(page.getByTestId("headline")).toContainText("dip around 28 Nov");
  await expect(page.getByText("Syarikat Kertas Sdn Bhd RM 18,400 is on hold until 6 Dec")).toBeVisible();

  await page.getByRole("link", { name: "Forecast" }).first().click();
  await expect(page.getByRole("heading", { name: "Forecast", level: 1 })).toBeVisible();
  await expect(page.getByText("What causes the dip")).toBeVisible();
  await expect(page.getByText("Minimum RM 20,000")).toBeVisible();

  await page.getByRole("link", { name: "Payments" }).first().click();
  await expect(page.getByText("Waiting for cash").first()).toBeVisible();
  await page.getByRole("button", { name: /Syarikat Kertas Sdn Bhd RM 18,400/ }).click();
  const dlg = page.getByRole("dialog");
  await expect(dlg).toContainText("Releasing on 6 Dec");
  await expect(dlg.getByText("Stays above your minimum")).toBeVisible();
  await expect(dlg.getByText("Failed").first()).toBeVisible();
  await dlg.getByRole("button", { name: "Show the numbers" }).click();
  await expect(dlg).toContainText("p_ok");
  await dlg.getByRole("button", { name: "Try paying today" }).click();
  await expect(dlg).toContainText("A dry run");
});

test("customer pays late: the band widens and an ALLOW flips to HOLD", async ({ page }) => {
  await page.goto("/payments");
  await expect(page.getByRole("button", { name: /Mesin Servis Teknik RM 12,000/ })).toContainText("Released");
  await openSimulator(page);
  await page.getByTestId("sim-late").click();
  const result = page.getByTestId("sim-result");
  await expect(result).toContainText("20 days late");
  await expect(result).toContainText("Typical width of the 80% range");
  await expect(result).toContainText("Mesin Servis Teknik");
  await page.keyboard.press("Escape");
  await page.goto("/payments");
  const row = page.getByRole("button", { name: /Mesin Servis Teknik RM 12,000/ });
  await expect(row).toContainText("Waiting for cash");
  await expect(row).toContainText("was: Released");
});

test("malicious invoice: ESCALATE on the approval card, hold it, no money moved, audit has the attempt", async ({ page }) => {
  await page.goto("/");
  await openSimulator(page);
  await page.getByTestId("sim-malicious").click();
  const card = page.getByRole("dialog", { name: "Approval card" });
  await expect(card).toBeVisible();
  await expect(card).toContainText("Pay Nexus Trading Supplies RM 48,000?");
  await expect(card).toContainText("Careful.");
  await card.getByRole("button", { name: "Ask why" }).click();
  await expect(card).toContainText("Why Helm stopped to ask");
  await card.getByRole("button", { name: "Approve" }).click();  // a quarantined invoice needs a second, deliberate tap
  await expect(card).toContainText("Approve anyway?");
  await card.getByRole("button", { name: "Cancel" }).click();
  await card.getByRole("button", { name: "Hold" }).click();
  await expect(card).toContainText("No money moved");

  const state = await (await page.request.get(`${API}/state`)).json();
  expect(state.operating).toBe(85000);
  const ledger = await (await page.request.get(`${API}/bank/ledger`)).json();
  expect(ledger.rows.length).toBe(0);

  await page.keyboard.press("Escape");
  await page.goto("/agents");
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText("Chain intact");
  await page.getByText("doc.quarantined").first().click();
  await expect(page.getByText("injection_like_text").first()).toBeVisible();
});

test("tampering with the audit log is caught and shown; the kill switch stops money", async ({ page }) => {
  await page.goto("/agents");
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText("Chain intact");

  await openSimulator(page);
  await page.getByTestId("sim-tamper").click();
  await page.keyboard.press("Escape");
  await page.getByTestId("verify-chain").click();
  await expect(page.getByTestId("verify-result")).toContainText("Chain broken at row");
  await expect(page.getByTestId("chain-banner")).toBeVisible();

  await resetDemo(page);
  await page.goto("/agents");
  await page.getByTestId("kill-switch").click();
  await expect(page.getByTestId("kill-state")).toContainText("ON");
  await openSimulator(page);
  await page.getByTestId("sim-advance").click();
  await expect(page.getByTestId("sim-result")).toContainText("0 payment(s) sent");
  const ledger = await (await page.request.get(`${API}/bank/ledger`)).json();
  expect(ledger.rows.length).toBe(0);
});

test("advance a week: payments are sent through the Demo bank with receipts", async ({ page }) => {
  await page.goto("/");
  await openSimulator(page);
  await page.getByTestId("sim-advance").click();
  await expect(page.getByTestId("sim-result")).toContainText("payment(s) sent");
  await page.keyboard.press("Escape");
  await page.goto("/payments");
  await expect(page.getByTestId("group-paid")).toContainText("Sent");
  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Demo bank statement" })).toBeVisible();
  await expect(page.getByText("accepted").first()).toBeVisible();
});

test("policy: change the risk slider, see a live preview, save", async ({ page }) => {
  await page.goto("/policy");
  await expect(page.getByTestId("sure-value")).toContainText("90% sure");
  const thumb = page.getByRole("slider");
  await thumb.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("sure-value")).toContainText("95% sure");
  await expect(page.getByTestId("policy-preview")).toBeVisible();
  await page.getByTestId("save-policy").click();
  await expect(page.getByText("Rules saved")).toBeVisible();
});

test("bahasa malaysia toggle and the command palette", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Switch language" }).click();
  await expect(page.getByRole("heading", { name: "Hari ini" })).toBeVisible();
  await page.keyboard.press("Control+k");
  await page.getByRole("combobox").fill("kertas");
  await expect(page.getByRole("option").first()).toContainText("Kertas");
});
