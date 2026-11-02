import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, writeHeader } from "../src/api";

/** A fetch that answers every request with `response`, and records what it was asked. */
function answering(response: Response | Error) {
  return vi.fn(async (_url: RequestInfo | URL, _init?: RequestInit) => {
    if (response instanceof Error) throw response;
    return response.clone();
  });
}

const json = (body: unknown, status = 200, statusText = "") =>
  new Response(JSON.stringify(body), { status, statusText, headers: { "Content-Type": "application/json" } });

describe("ApiClient", () => {
  it("reads JSON from under its base, asking for JSON", async () => {
    const fetcher = answering(json({ id: 1 }));
    const client = new ApiClient({ fetcher });

    expect(await client.request("GET", "/items/1")).toEqual({ id: 1 });
    const [url, init] = fetcher.mock.calls[0]!;
    expect(url).toBe("/api/items/1");
    expect(init).toMatchObject({ method: "GET", credentials: "same-origin", body: undefined });
    expect(init!.headers).toEqual({ Accept: "application/json" });
  });

  it("sends JSON with the write header on a write, and never on a read", async () => {
    const fetcher = answering(json({ ok: true }, 201));
    const client = new ApiClient({ base: "/api/v2", fetcher, writeHeader: writeHeader("myapp") });

    await client.request("POST", "/items", { name: "a" });
    await client.request("head", "/items");
    const [url, write] = fetcher.mock.calls[0]!;
    expect(url).toBe("/api/v2/items");
    expect(write!.headers).toEqual({
      Accept: "application/json",
      "Content-Type": "application/json",
      "X-Requested-With": "myapp",
    });
    expect(write!.body).toBe('{"name":"a"}');
    expect(fetcher.mock.calls[1]![1]!.headers).toEqual({ Accept: "application/json" });
  });

  it("sends a form as it is", async () => {
    const fetcher = answering(json({}));
    const form = new FormData();
    form.append("file", "x");

    await new ApiClient({ fetcher }).request("POST", "/upload", form);
    const init = fetcher.mock.calls[0]![1]!;
    expect(init.body).toBe(form);
    expect(init.headers).toEqual({ Accept: "application/json" });
  });

  it("answers a 204 with undefined", async () => {
    const client = new ApiClient({ fetcher: answering(new Response(null, { status: 204 })) });
    expect(await client.request("DELETE", "/items/1")).toBeUndefined();
  });

  it("builds a query from the values that are set, with the client's own last", async () => {
    const client = new ApiClient({ query: () => ({ lang: "pt-PT" }) });

    expect(client.url("/items", { year: 2026, q: "", page: null, all: undefined, open: false, lang: "en" })).toBe(
      "/api/items?year=2026&open=false&lang=pt-PT",
    );
    expect(new ApiClient().url("/items")).toBe("/api/items");
    expect(new ApiClient().url("/items", { a: "b c&d" })).toBe("/api/items?a=b+c%26d");
  });

  it("sends the query with the request", async () => {
    const fetcher = answering(json([]));
    await new ApiClient({ fetcher }).request("GET", "/items", undefined, { year: 2026 });
    expect(fetcher.mock.calls[0]![0]).toBe("/api/items?year=2026");
  });

  it("uses the global fetch by default", async () => {
    const fetched = vi.spyOn(globalThis, "fetch").mockResolvedValue(json({ ok: 1 }));
    expect(await new ApiClient().request("GET", "/health")).toEqual({ ok: 1 });
    expect(fetched).toHaveBeenCalledOnce();
    fetched.mockRestore();
  });
});

describe("failures", () => {
  async function failure(client: ApiClient): Promise<ApiError> {
    const error = await client.request("GET", "/x").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    return error as ApiError;
  }

  it("carries the server's own code", async () => {
    const error = await failure(new ApiClient({ fetcher: answering(json({ detail: "no_rule" }, 409)) }));
    expect([error.status, error.message, error.name]).toEqual([409, "no_rule", "ApiError"]);
  });

  it("calls a list of validation errors invalid", async () => {
    const error = await failure(new ApiClient({ fetcher: answering(json({ detail: [{ loc: ["x"] }] }, 422)) }));
    expect([error.status, error.message]).toEqual([422, "invalid"]);
  });

  it("falls back to the status text, or the status, without a reason", async () => {
    const page = new Response("<html>bad gateway</html>", { status: 502, statusText: "Bad Gateway" });
    expect((await failure(new ApiClient({ fetcher: answering(page) }))).message).toBe("Bad Gateway");
    const bare = new Response("{}", { status: 500 });
    expect((await failure(new ApiClient({ fetcher: answering(bare) }))).message).toBe("HTTP 500");
  });

  it("words a failure without a reason as the application asks", async () => {
    const client = new ApiClient({
      fetcher: answering(new Response("nope", { status: 503, statusText: "Unavailable" })),
      failed: (status, text) => `failed ${status} ${text}`,
    });
    expect((await failure(client)).message).toBe("failed 503 Unavailable");
  });

  it("is status 0 when the server cannot be reached", async () => {
    const error = await failure(new ApiClient({ fetcher: answering(new TypeError("Failed to fetch")) }));
    expect([error.status, error.message]).toEqual([0, "Failed to fetch"]);
  });

  it("words an unreachable server as the application asks, or from whatever was thrown", async () => {
    const worded = new ApiClient({ fetcher: answering(new TypeError("x")), unreachable: () => "offline" });
    expect((await failure(worded)).message).toBe("offline");
    const thrower = new ApiClient({ fetcher: vi.fn().mockRejectedValue("plain") });
    expect((await failure(thrower)).message).toBe("plain");
  });
});
