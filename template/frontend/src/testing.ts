/** A fake API for the interface's tests: the real client, over a fetch that answers from a table. */

import type { Authenticator } from "@jmerhar/jigkit/passkeys";
import { vi } from "vitest";
import { Api, type Me } from "./lib/api";

/** An answer: a body for 200, or a status with a body (a code for a refusal), or a function. */
export type Answer = unknown | { status: number; body?: unknown } | ((body: unknown) => unknown);

/** A refusal with the API's code. */
export const refuse = (status: number, detail: string) => ({ status, body: { detail } });

export const ME: Me = { id: 1, name: "Ana", login: "ana", language: null, notifications: true };

/** An Api whose requests are answered from `answers`, keyed "METHOD /path", and recorded. */
export function fakeApi(answers: Record<string, Answer>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetcher = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const path = String(url).replace(/^\/api/, "").split("?")[0]!;
    const method = init?.method ?? "GET";
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined;
    calls.push({ method, path, body });
    let answer = answers[`${method} ${path}`];
    if (typeof answer === "function") answer = (answer as (body: unknown) => unknown)(body);
    if (answer === undefined) return new Response(null, { status: 204 });
    const { status, body: payload } =
      answer && typeof answer === "object" && "status" in answer
        ? (answer as { status: number; body?: unknown })
        : { status: 200, body: answer };
    return new Response(payload === undefined ? null : JSON.stringify(payload), { status });
  });
  return { api: new Api("/api", fetcher as unknown as typeof fetch), calls };
}

/** An authenticator that answers at once, with the given abilities. */
export function fakeAuthenticator(overrides: Partial<Authenticator> = {}): Authenticator {
  return {
    supported: () => true,
    autofill: async () => false,
    builtIn: async () => false,
    register: vi.fn(async () => ({ made: true })),
    authenticate: vi.fn(async () => ({ pressed: true })),
    cancel: vi.fn(),
    ...overrides,
  };
}
