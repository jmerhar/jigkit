/**
 * The core of an API client: one request, JSON or a form in and JSON out, and every failure as an
 * {@link ApiError}. An application extends {@link ApiClient} with a method per endpoint, typed from
 * its OpenAPI schema:
 *
 *     class Api extends ApiClient {
 *       constructor() { super({ writeHeader: writeHeader("myapp") }); }
 *       items = () => this.request<Item[]>("GET", "/items");
 *     }
 */

/** A query string's values; empty, null and undefined values are left out. */
export type Query = Record<string, string | number | boolean | undefined | null>;

/**
 * A request that failed: its HTTP status (0 when the server could not be reached) and the reason,
 * which for the API's own refusals is the code it sent as `detail`, such as "no_rule".
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** 401's code: the request needs a logged-in session and has none. Python's `jigkit.refusals`. */
export const NOT_AUTHENTICATED = "not_authenticated";

/** 409's code: the application has no administrator yet, and first-run setup comes first. */
export const SETUP_REQUIRED = "setup_required";

/**
 * FastAPI's validation errors as one reason: each one's `msg`, joined with "; ", or "invalid" when
 * none has one. For the `invalid` option of an interface that shows the server's own sentences.
 */
export function fieldMessages(detail: unknown[]): string {
  const messages = detail
    .map((item) => (item && typeof item === "object" ? (item as { msg?: unknown }).msg : undefined))
    .filter((msg): msg is string => typeof msg === "string" && msg !== "");
  return messages.length > 0 ? messages.join("; ") : "invalid";
}

/** The header the API's write guard (`jigkit.web.install_write_guard`) wants on every write. */
export function writeHeader(value: string): Record<string, string> {
  return { "X-Requested-With": value };
}

export interface ClientOptions {
  /** Where the API is, relative to the page's origin by default. */
  base?: string;
  /** The fetch to use; a test passes its own. */
  fetcher?: typeof fetch;
  /** Headers every write (any method but GET and HEAD) carries, such as {@link writeHeader}'s. */
  writeHeader?: Record<string, string>;
  /** Parameters added to every request's query, such as the interface's language. */
  query?: () => Query;
  /** The message of the error for a server that could not be reached. */
  unreachable?: (error: unknown) => string;
  /** The message of the error for a failure the server gave no reason for. */
  failed?: (status: number, statusText: string) => string;
  /**
   * The reason for FastAPI's list of validation errors, "invalid" without it; {@link fieldMessages}
   * gives each field's message.
   */
  invalid?: (detail: unknown[]) => string;
  /**
   * The application's own error for a refusal, such as one for {@link NOT_AUTHENTICATED} that
   * sends the interface to its login; undefined leaves it an {@link ApiError}.
   */
  refused?: (status: number, reason: string) => Error | undefined;
}

const READS = new Set(["GET", "HEAD"]);

/** The fetch and error handling an application's API client is built on. */
export class ApiClient {
  readonly base: string;
  private readonly fetcher: typeof fetch;
  private readonly options: ClientOptions;

  constructor(options: ClientOptions = {}) {
    this.base = options.base ?? "/api";
    this.fetcher = options.fetcher ?? ((...args) => fetch(...args));
    this.options = options;
  }

  /**
   * The URL of `path` under the API with `query`, for a link or a download as much as a request.
   * Built from the query's text rather than `URLSearchParams.size`, which Safari before 17 lacks.
   */
  url(path: string, query: Query = {}): string {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries({ ...query, ...this.options.query?.() })) {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    }
    const search = params.toString();
    return this.base + path + (search ? `?${search}` : "");
  }

  /**
   * One request. A FormData body goes as a form, anything else defined as JSON. A 204 answers
   * undefined; any other success, its JSON.
   */
  async request<T>(method: string, path: string, body?: unknown, query: Query = {}): Promise<T> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (!READS.has(method.toUpperCase())) Object.assign(headers, this.options.writeHeader);
    let payload: BodyInit | undefined;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let response: Response;
    try {
      response = await this.fetcher(this.url(path, query), {
        method,
        headers,
        body: payload,
        credentials: "same-origin",
      });
    } catch (error) {
      const message = this.options.unreachable?.(error) ?? (error instanceof Error ? error.message : String(error));
      throw new ApiError(0, message);
    }
    if (!response.ok) {
      const reason = await this.reason(response);
      throw this.options.refused?.(response.status, reason) ?? new ApiError(response.status, reason);
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  /**
   * Why a request failed: the server's `detail` when it is a code or a sentence, the `invalid`
   * option's reason (or "invalid") for FastAPI's list of validation errors, else the `failed`
   * option's message or the status text.
   * A proxy's error page is not JSON, and falls through to the status.
   */
  private async reason(response: Response): Promise<string> {
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") return body.detail;
      if (Array.isArray(body.detail)) return this.options.invalid?.(body.detail) ?? "invalid";
    } catch {
      // Not JSON.
    }
    return this.options.failed?.(response.status, response.statusText) ?? (response.statusText || `HTTP ${response.status}`);
  }
}
