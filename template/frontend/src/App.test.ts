import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.svelte";
import { LANGUAGE_KEY } from "./lib/language";
import { ME, fakeApi, fakeAuthenticator, refuse } from "./testing";

afterEach(() => {
  localStorage.clear();
  location.hash = "";
});

/** Open the navigation's menu whose button starts with `name`. */
const openMenu = async (name: string) => fireEvent.click(await screen.findByRole("button", { name: new RegExp(`^${name}`) }));

async function fill(label: string | RegExp, value: string): Promise<void> {
  await fireEvent.input(screen.getByLabelText(label), { target: { value } });
}

describe("starting", () => {
  it("asks for the first account on a new installation, and opens the notes once made", async () => {
    const { api, calls } = fakeApi({ "GET /setup": { required: true }, "POST /setup": ME, "GET /notes": [] });
    render(App, { api, authenticator: fakeAuthenticator() });

    await screen.findByRole("heading", { name: "Welcome" });
    await fill("Name", "Ana");
    await fill("Username", "ana");
    await fill(/^Password/, "correct horse battery");
    await fireEvent.submit((await screen.findByRole("button", { name: "Create the account" })).closest("form")!);

    expect(await screen.findByRole("heading", { name: "Notes" })).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/setup" && call.method === "POST")!.body).toEqual({
      name: "Ana",
      login: "ana",
      password: "correct horse battery",
      language: null,
    });
  });

  it("logs in, and logs out again", async () => {
    const { api } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/login": ME,
      "GET /notes": [],
    });
    render(App, { api, authenticator: fakeAuthenticator() });

    await screen.findByRole("heading", { name: "Log in" });
    await fill("Username", "ana");
    await fill("Password", "correct horse battery");
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    expect(await screen.findByRole("heading", { name: "Notes" })).toBeInTheDocument();

    await openMenu("Ana");
    await fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("offers a passkey after a password login on a device that can make one", async () => {
    const { api } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/login": ME,
      "GET /notes": [],
    });
    render(App, { api, authenticator: fakeAuthenticator({ builtIn: async () => true }) });

    await screen.findByRole("heading", { name: "Log in" });
    await fill("Username", "ana");
    await fill("Password", "correct horse battery");
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);

    expect(await screen.findByRole("button", { name: "Set it up" })).toBeInTheDocument();
  });

  it("opens straight away for a browser already logged in, and moves between pages", async () => {
    const { api } = fakeApi({ "GET /setup": { required: false }, "GET /auth/me": ME, "GET /notes": [], "GET /auth/passkeys": [] });
    render(App, { api, authenticator: fakeAuthenticator() });

    await screen.findByRole("heading", { name: "Notes" });
    expect(screen.getByRole("link", { name: "Notes" })).toHaveAttribute("aria-current", "page");
    await openMenu("Ana");
    await fireEvent.click(screen.getByRole("link", { name: "Account" }));
    expect(await screen.findByRole("heading", { name: "Account" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Ana/ })).toHaveClass("current");
    await fireEvent.click(screen.getByRole("link", { name: "Notes" }));
    expect(await screen.findByRole("heading", { name: "Notes" })).toBeInTheDocument();
  });

  it("switches the theme and the language from the account's menu", async () => {
    const reload = vi.fn();
    const { api, calls } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": ME,
      "GET /notes": [],
      "PUT /account": { ...ME, language: "pt-PT" },
    });
    render(App, { api, authenticator: fakeAuthenticator(), reload });
    await openMenu("Ana");

    await fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(document.documentElement.dataset.theme).toBe("dark");
    await fireEvent.click(screen.getByRole("button", { name: "As the device" }));
    expect(document.documentElement.dataset.theme).toBeUndefined();

    await fireEvent.click(screen.getByRole("button", { name: "As the browser" }));
    expect(calls.some((call) => call.method === "PUT")).toBe(false);
    await fireEvent.click(screen.getByRole("button", { name: "PT" }));
    await waitFor(() => expect(reload).toHaveBeenCalledOnce());
    expect(calls.find((call) => call.method === "PUT")!.body).toEqual({ name: "Ana", language: "pt-PT" });
  });

  it("follows the language saved on the account", async () => {
    const reload = vi.fn();
    const { api } = fakeApi({ "GET /setup": { required: false }, "GET /auth/me": { ...ME, language: "pt-PT" } });
    render(App, { api, authenticator: fakeAuthenticator(), reload });

    await waitFor(() => expect(reload).toHaveBeenCalledOnce());
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("pt-PT");
  });

  it("says why it could not start", async () => {
    const { api } = fakeApi({ "GET /setup": refuse(500, "boom") });
    render(App, { api, authenticator: fakeAuthenticator() });

    expect(await screen.findByRole("alert")).toHaveTextContent("The app could not start: Something went wrong (boom).");
  });

  it("logs in with a passkey, and sets one up when offered", async () => {
    const { api, calls } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/passkey-login/options": { challenge: "c" },
      "POST /auth/passkey-login": ME,
      "POST /auth/login": ME,
      "POST /auth/passkeys/options": { challenge: "r" },
      "POST /auth/passkeys": { id: 1, label: "Mac", created_at: "2026-10-18T14:05:00Z", last_used_at: null },
      "GET /notes": [],
    });
    const { unmount } = render(App, { api, authenticator: fakeAuthenticator() });
    await fireEvent.click(await screen.findByRole("button", { name: "Log in with a passkey" }));
    expect(await screen.findByRole("heading", { name: "Notes" })).toBeInTheDocument();
    expect(calls.find((call) => call.path === "/auth/passkey-login")!.body).toEqual({ credential: { pressed: true } });
    unmount();
    localStorage.clear();

    render(App, { api, authenticator: fakeAuthenticator({ builtIn: async () => true }) });
    await screen.findByRole("heading", { name: "Log in" });
    await fill("Username", "ana");
    await fill("Password", "correct horse battery");
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    await fireEvent.click(await screen.findByRole("button", { name: "Set it up" }));
    expect(await screen.findByText("Done: next time, log in with your passkey.")).toBeInTheDocument();
    expect(calls.some((call) => call.method === "POST" && call.path === "/auth/passkeys")).toBe(true);
  });

  it("logs out even when the server cannot be told", async () => {
    const { api } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": ME,
      "GET /notes": [],
      "POST /auth/logout": refuse(500, "boom"),
    });
    render(App, { api, authenticator: fakeAuthenticator() });
    await openMenu("Ana");
    await fireEvent.click(await screen.findByRole("button", { name: "Log out" }));
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeInTheDocument();
  });

  it("follows the account's language after logging in", async () => {
    const reload = vi.fn();
    const { api } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/login": { ...ME, language: "pt-PT" },
    });
    render(App, { api, authenticator: fakeAuthenticator(), reload });
    await screen.findByRole("heading", { name: "Log in" });
    await fill("Username", "ana");
    await fill("Password", "correct horse battery");
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    await waitFor(() => expect(reload).toHaveBeenCalledOnce());
  });

  it("says why setup or a login failed", async () => {
    const { api } = fakeApi({ "GET /setup": { required: true }, "POST /setup": refuse(409, "already_set_up") });
    const { unmount } = render(App, { api, authenticator: fakeAuthenticator() });
    await screen.findByRole("heading", { name: "Welcome" });
    await fireEvent.submit(screen.getByRole("button", { name: "Create the account" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("The app is already set up; log in instead.");
    unmount();

    const login = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/login": refuse(401, "invalid_login"),
    });
    render(App, { api: login.api, authenticator: fakeAuthenticator() });
    await screen.findByRole("heading", { name: "Log in" });
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("That username and password do not match.");
  });

  it("puts the passkey offer away, and explains a failed one", async () => {
    const { api } = fakeApi({
      "GET /setup": { required: false },
      "GET /auth/me": refuse(401, "not_authenticated"),
      "POST /auth/login": ME,
      "POST /auth/passkeys/options": refuse(400, "passkey_expired"),
      "GET /notes": [],
    });
    render(App, { api, authenticator: fakeAuthenticator({ builtIn: async () => true }) });
    await screen.findByRole("heading", { name: "Log in" });
    await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
    await fireEvent.click(await screen.findByRole("button", { name: "Set it up" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("That took too long; try again.");
    await fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Set it up" })).not.toBeInTheDocument());
  });
});
