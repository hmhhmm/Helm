import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const API = "http://localhost:8000";

export async function ownerToken(request: APIRequestContext): Promise<string> {
  const r = await request.post(`${API}/auth/login`, { data: { passcode: "helm-demo" } });
  expect(r.ok()).toBeTruthy();
  return (await r.json()).token;
}

/** Makes this page act as the logged in owner (the token goes into localStorage before any script runs). */
export async function asOwner(page: Page): Promise<{ Authorization: string }> {
  const token = await ownerToken(page.request);
  await page.addInitScript((t) => localStorage.setItem("helm-token", t), token);
  return { Authorization: `Bearer ${token}` };
}

export async function resetDemo(page: Page) {
  const token = await ownerToken(page.request);
  const r = await page.request.post(`${API}/sim/reset`, { headers: { Authorization: `Bearer ${token}` } });
  expect(r.ok()).toBeTruthy();
}

export async function openSimulator(page: Page) {
  await page.getByTestId("date-control").click();
  await expect(page.getByRole("dialog", { name: "Simulator" })).toBeVisible();
}
