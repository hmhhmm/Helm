import createClient from "openapi-fetch";
import { getToken, LOGIN_EVENT } from "./auth";
import type { components, paths } from "./api-schema";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const api = createClient<paths>({ baseUrl: API_URL });

// State changing calls need an owner token. If the server says 401, ask the person to log in.
api.use({
  onRequest({ request }) {
    const t = getToken();
    if (t) request.headers.set("Authorization", `Bearer ${t}`);
    return request;
  },
  onResponse({ response }) {
    if (response.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event(LOGIN_EVENT));
    return response;
  },
});

export type Schemas = components["schemas"];
export type Row = Schemas["Row"];
export type Verdict = Schemas["Row"]["verdict"];
export type Txt = Schemas["Txt"];
export type ForecastOut = Schemas["ForecastOut"];
export type Event = Schemas["Event"];

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

/** Unwraps an openapi-fetch result, turning API problems into readable errors. */
export function unwrap<T>(res: { data?: T; error?: unknown; response: Response }): T {
  if (res.data !== undefined) return res.data;
  const detail = (res.error as { detail?: unknown } | undefined)?.detail;
  const msg = typeof detail === "string" ? detail : res.response?.statusText || "Request failed";
  throw new ApiError(msg, res.response?.status);
}

export const briefUrl = `${API_URL}/brief.pdf`;
