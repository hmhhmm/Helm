import { expect, type Page } from "@playwright/test";

export const API = "http://localhost:8000";

export async function resetDemo(page: Page) {
  const r = await page.request.post(`${API}/sim/reset`);
  expect(r.ok()).toBeTruthy();
}

export async function openSimulator(page: Page) {
  await page.getByTestId("date-control").click();
  await expect(page.getByRole("dialog", { name: "Simulator" })).toBeVisible();
}
