import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../src/api";
import {
  alreadyAdded,
  LoginForm,
  PasskeyList,
  PasskeyOffer,
  SetupForm,
  WelcomeForm,
  type PasskeyItem,
} from "../src/auth/svelte";
import { passkeyMemory } from "../src/passkeys";
import { autofilling, errorMessage, fakeAuthenticator, LIST, LOGIN, named, OFFER, SETUP } from "./auth.helpers";
import { MemoryStorage } from "./helpers";

afterEach(() => {
  vi.useRealTimers();
});

const icon = (text: string) => createRawSnippet(() => ({ render: () => `<i>${text}</i>` }));

function loginForm(props: Record<string, unknown> = {}) {
  const memory = passkeyMemory("myapp", new MemoryStorage());
  const onDone = vi.fn();
  const logIn = vi.fn(async () => undefined);
  const passkeys = { options: vi.fn(async () => ({ challenge: "c" })), logIn: vi.fn(async () => undefined) };
  const result = render(LoginForm, {
    title: "My app",
    labels: LOGIN,
    logIn,
    passkeys,
    memory,
    authenticator: fakeAuthenticator(),
    errorMessage,
    onDone,
    ...props,
  });
  return { ...result, memory, onDone, logIn, passkeys };
}

async function submitPassword(login = "ana", password = "correct horse"): Promise<void> {
  await fireEvent.input(screen.getByLabelText("Username"), { target: { value: login } });
  await fireEvent.input(screen.getByLabelText("Password"), { target: { value: password } });
  await fireEvent.submit(screen.getByRole("button", { name: "Log in" }).closest("form")!);
}

describe("LoginForm with a password", () => {
  it("logs in, and offers a passkey on a device that can make one", async () => {
    const { logIn, onDone } = loginForm();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("My app");

    await submitPassword();

    expect(logIn).toHaveBeenCalledWith("ana", "correct horse");
    await waitFor(() => expect(onDone).toHaveBeenCalledWith({ offerPasskey: true }));
  });

  it("makes no offer without a reader, once turned down, once a passkey was used, or without passkeys", async () => {
    const reader = fakeAuthenticator({ builtIn: async () => false });
    const cases: [Record<string, unknown>, (memory: ReturnType<typeof passkeyMemory>) => void][] = [
      [{ authenticator: reader }, () => {}],
      [{}, (memory) => memory.declineOffer()],
      [{ authenticator: fakeAuthenticator({ builtIn: async () => Promise.reject(new Error("x")) }) }, () => {}],
    ];
    for (const [props, prepare] of cases) {
      const storage = new MemoryStorage();
      const memory = passkeyMemory("myapp", storage);
      prepare(memory);
      const { onDone, unmount } = loginForm({ ...props, memory });
      await submitPassword();
      await waitFor(() => expect(onDone).toHaveBeenCalledWith({ offerPasskey: false }));
      unmount();
    }
    const { onDone } = loginForm({ passkeys: undefined, memory: undefined });
    await submitPassword();
    await waitFor(() => expect(onDone).toHaveBeenCalledWith({ offerPasskey: false }));
  });

  it("says why a login failed, and can be tried again", async () => {
    const { onDone } = loginForm({ logIn: vi.fn(async () => Promise.reject(new Error("invalid_login"))) });
    await submitPassword();
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: invalid_login");
    expect(screen.getByRole("button", { name: "Log in" })).toBeEnabled();
    expect(onDone).not.toHaveBeenCalled();
  });

  it("offers passwords only without a passkey half or a browser that has passkeys", () => {
    const { unmount } = loginForm({ passkeys: undefined });
    expect(screen.queryByRole("button", { name: "Log in with a passkey" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username");
    unmount();
    loginForm({ authenticator: fakeAuthenticator({ supported: () => false }) });
    expect(screen.queryByRole("button", { name: "Log in with a passkey" })).not.toBeInTheDocument();
  });
});

describe("LoginForm with a passkey", () => {
  it("is a quiet link after the password where none has been used, and logs in from it", async () => {
    const { passkeys, memory, onDone } = loginForm({ icon: icon("fingerprint") });
    const link = screen.getByRole("button", { name: "Log in with a passkey" });
    expect(link).toHaveClass("link");
    expect(link.querySelector("i")).toBeNull();

    await fireEvent.click(link);

    await waitFor(() => expect(onDone).toHaveBeenCalledWith({ offerPasskey: false }));
    expect(passkeys.logIn).toHaveBeenCalledWith({ pressed: true });
    expect(memory.usedHere()).toBe(true);
  });

  it("comes first, with the icon, on a browser that has used one", () => {
    const memory = passkeyMemory("myapp", new MemoryStorage());
    memory.rememberUsed();
    loginForm({ memory, icon: icon("fingerprint") });
    const button = screen.getByRole("button", { name: "fingerprint Log in with a passkey" });
    expect(button).toHaveClass("wide-button");
    expect(screen.getByText("or with your password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log in" })).toHaveClass("secondary");
  });

  it("is offered among the login field's autofill suggestions", async () => {
    const passkey = autofilling();
    const { passkeys, onDone } = loginForm({ authenticator: passkey.authenticator });
    expect(screen.getByLabelText("Username")).toHaveAttribute("autocomplete", "username webauthn");
    await waitFor(() => expect(passkey.requests).toEqual([true]));

    passkey.pick({ picked: true });

    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
    expect(passkeys.logIn).toHaveBeenCalledWith({ picked: true });
  });

  it("renews the waiting request before the challenge expires, and stops it on leaving", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const passkey = autofilling();
    const { passkeys, unmount } = loginForm({ authenticator: passkey.authenticator });
    await waitFor(() => expect(passkey.requests).toEqual([true]));

    vi.advanceTimersByTime(240_000);
    await waitFor(() => expect(passkey.requests).toEqual([true, true]));
    expect(passkeys.options).toHaveBeenCalledTimes(2);
    // The renewal cancels the first request, which is no failure to report.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    unmount();
    expect(passkey.authenticator.cancel).toHaveBeenCalledTimes(2);
    vi.advanceTimersByTime(240_000);
    expect(passkey.requests).toHaveLength(2);
  });

  it("stops the waiting request for the button, and waits again if the button is dismissed", async () => {
    const passkey = autofilling();
    passkey.authenticator.authenticate = (_options, autofill = false) => {
      passkey.requests.push(autofill);
      return autofill ? new Promise(() => undefined) : Promise.reject(named("NotAllowedError"));
    };
    loginForm({ authenticator: passkey.authenticator });
    await waitFor(() => expect(passkey.requests).toEqual([true]));

    await fireEvent.click(screen.getByRole("button", { name: "Log in with a passkey" }));

    await waitFor(() => expect(passkey.requests).toEqual([true, false, true]));
    expect(passkey.authenticator.cancel).toHaveBeenCalledOnce();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("says what went wrong with a passkey, from the button or the autofill", async () => {
    const { unmount } = loginForm({
      passkeys: { options: async () => ({}), logIn: async () => Promise.reject(new Error("passkey_unknown")) },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Log in with a passkey" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: passkey_unknown");
    unmount();

    const passkey = autofilling();
    loginForm({
      authenticator: passkey.authenticator,
      passkeys: { options: async () => ({}), logIn: async () => Promise.reject(new Error("passkey_rejected")) },
    });
    await waitFor(() => expect(passkey.requests).toEqual([true]));
    passkey.pick({});
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: passkey_rejected");
  });

  it("falls back to the button when the browser cannot say whether it autofills", async () => {
    const authenticator = fakeAuthenticator({ autofill: async () => Promise.reject(new Error("unknown")) });
    loginForm({ authenticator });
    await Promise.resolve();
    expect(authenticator.authenticate).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Log in with a passkey" })).toBeInTheDocument();
  });
});

describe("SetupForm", () => {
  it("creates the first account after the application's own fields", async () => {
    const setUp = vi.fn(async () => undefined);
    const onDone = vi.fn();
    render(SetupForm, {
      labels: SETUP,
      setUp,
      errorMessage,
      onDone,
      minPasswordLength: 12,
      children: createRawSnippet(() => ({ render: () => `<label>Household<input name="household" /></label>` })),
    });
    const fields = [...document.querySelectorAll("label")].map((label) => label.textContent?.trim().split("\n")[0]);
    expect(fields[0]).toBe("Household");
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute("minlength", "12");

    await fireEvent.input(screen.getByLabelText("Name"), { target: { value: "Ana" } });
    await fireEvent.input(screen.getByLabelText("Username"), { target: { value: "ana" } });
    await fireEvent.input(screen.getByLabelText(/^Password/), { target: { value: "a long password" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Create" }).closest("form")!);

    expect(setUp).toHaveBeenCalledWith({ name: "Ana", login: "ana", password: "a long password" });
    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
  });

  it("says why setting up failed", async () => {
    const onDone = vi.fn();
    render(SetupForm, { labels: SETUP, setUp: async () => Promise.reject(new Error("already_set_up")), errorMessage, onDone });
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute("minlength", "10");
    await fireEvent.submit(screen.getByRole("button", { name: "Create" }).closest("form")!);
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: already_set_up");
    expect(onDone).not.toHaveBeenCalled();
  });
});

const WELCOME = {
  heading: "Welcome",
  intro: "Choose a password for your account, Ana.",
  login: "Username",
  password: "Password",
  passwordHint: "At least 10 characters.",
  repeat: "The password again",
  mismatch: "The two passwords differ.",
  submit: "Save the password",
  submitting: "Saving…",
};

describe("WelcomeForm", () => {
  it("shows the login, and sets the password typed twice", async () => {
    const accept = vi.fn(async () => undefined);
    const onDone = vi.fn();
    render(WelcomeForm, { labels: WELCOME, login: "ana", accept, errorMessage, onDone, minPasswordLength: 12 });

    expect(screen.getByLabelText("Username")).toHaveValue("ana");
    expect(screen.getByLabelText("Username")).toHaveAttribute("readonly");
    expect(screen.getByLabelText(/^Password/)).toHaveAttribute("minlength", "12");
    await fireEvent.input(screen.getByLabelText(/^Password/), { target: { value: "a long password" } });
    await fireEvent.input(screen.getByLabelText("The password again"), { target: { value: "a long password" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save the password" }).closest("form")!);

    expect(accept).toHaveBeenCalledWith("a long password");
    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
  });

  it("refuses two different passwords without asking the server", async () => {
    const accept = vi.fn(async () => undefined);
    render(WelcomeForm, { labels: WELCOME, login: "ana", accept, errorMessage, onDone: vi.fn() });
    await fireEvent.input(screen.getByLabelText(/^Password/), { target: { value: "a long password" } });
    await fireEvent.input(screen.getByLabelText("The password again"), { target: { value: "a long passwerd" } });
    await fireEvent.submit(screen.getByRole("button", { name: "Save the password" }).closest("form")!);

    expect(screen.getByRole("alert")).toHaveTextContent("The two passwords differ.");
    expect(accept).not.toHaveBeenCalled();
  });

  it("says why the link was refused", async () => {
    const onDone = vi.fn();
    render(WelcomeForm, {
      labels: WELCOME,
      login: "ana",
      accept: async () => Promise.reject(new Error("invitation_expired")),
      errorMessage,
      onDone,
    });
    await fireEvent.submit(screen.getByRole("button", { name: "Save the password" }).closest("form")!);

    expect(await screen.findByRole("alert")).toHaveTextContent("failed: invitation_expired");
    expect(onDone).not.toHaveBeenCalled();
  });
});

function offer(props: Record<string, unknown> = {}) {
  const memory = passkeyMemory("myapp", new MemoryStorage());
  const registration = { options: vi.fn(async () => ({ challenge: "c" })), add: vi.fn(async () => ({})) };
  const authenticator = fakeAuthenticator();
  render(PasskeyOffer, { open: true, labels: OFFER, registration, memory, authenticator, errorMessage, label: "iPhone", ...props });
  return { memory, registration, authenticator };
}

describe("PasskeyOffer", () => {
  it("sets a passkey up in one tap, then closes", async () => {
    const { memory, registration } = offer();
    await fireEvent.click(screen.getByRole("button", { name: "Set it up" }));

    expect(await screen.findByText("Done: next time, use your fingerprint.")).toBeInTheDocument();
    expect(registration.add).toHaveBeenCalledWith("iPhone", { made: true });
    expect(memory.usedHere()).toBe(true);
    await fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("is turned down for this browser", async () => {
    const { memory } = offer();
    await fireEvent.click(screen.getByRole("button", { name: "Not now" }));
    expect(memory.offerDeclined()).toBe(true);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("goes away when the device has one already", async () => {
    const { memory } = offer({
      registration: { options: async () => ({}), add: async () => Promise.reject(new ApiError(409, "passkey_exists")) },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Set it up" }));
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(memory.usedHere()).toBe(true);
  });

  it("says nothing when dismissed, and explains a refusal", async () => {
    offer({ authenticator: fakeAuthenticator({ register: async () => Promise.reject(named("NotAllowedError")) }) });
    await fireEvent.click(screen.getByRole("button", { name: "Set it up" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Set it up" })).toBeEnabled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    document.body.innerHTML = "";

    offer({ registration: { options: async () => Promise.reject(new ApiError(500, "boom")), add: vi.fn() } });
    await fireEvent.click(screen.getByRole("button", { name: "Set it up" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: boom");
  });

  it("shows nothing while closed", () => {
    offer({ open: false });
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("names the passkey after the device by default", async () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (Macintosh)");
    const { registration } = offer({ label: undefined });
    await fireEvent.click(screen.getByRole("button", { name: "Set it up" }));
    await waitFor(() => expect(registration.add).toHaveBeenCalledWith("Mac", { made: true }));
    vi.restoreAllMocks();
  });
});

const ITEMS: PasskeyItem[] = [
  { id: 1, label: "iPhone", last_used_at: "2026-10-18T14:05:00Z" },
  { id: 2, label: "Laptop", last_used_at: null },
];

function list(props: Record<string, unknown> = {}) {
  const registration = { options: vi.fn(async () => ({})), add: vi.fn(async (label: string) => ({ id: 3, label, last_used_at: null })) };
  const remove = vi.fn(async () => undefined);
  const result = render(PasskeyList, {
    passkeys: ITEMS,
    labels: LIST,
    registration,
    remove,
    formatWhen: (iso: string) => iso.slice(0, 10),
    errorMessage,
    authenticator: fakeAuthenticator(),
    ask: () => "  Work phone ",
    confirmRemove: () => true,
    addIcon: icon("+"),
    removeIcon: icon("x"),
    ...props,
  });
  return { ...result, registration, remove };
}

describe("PasskeyList", () => {
  it("lists passkeys with when each was last used", () => {
    list();
    const items = screen.getAllByRole("listitem").map((item) => item.textContent?.replace(/\s+/g, " ").trim());
    expect(items).toEqual(["iPhone Last used 2026-10-18 xRemove", "Laptop Never used xRemove"]);
  });

  it("adds a passkey under the name given, or the device's", async () => {
    const { registration } = list();
    await fireEvent.click(screen.getByRole("button", { name: "+Add a passkey" }));
    expect(await screen.findByText("Work phone")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Passkey added.");
    expect(registration.add).toHaveBeenCalledWith("Work phone", { made: true });
    document.body.innerHTML = "";

    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (Windows NT 10.0)");
    const again = list({ ask: () => null });
    await fireEvent.click(screen.getByRole("button", { name: "+Add a passkey" }));
    await waitFor(() => expect(again.registration.add).toHaveBeenCalledWith("Windows", { made: true }));
    vi.restoreAllMocks();
  });

  it("removes a passkey once confirmed", async () => {
    const { remove } = list();
    await fireEvent.click(screen.getAllByRole("button", { name: "xRemove" })[1]!);
    await waitFor(() => expect(screen.queryByText("Laptop")).not.toBeInTheDocument());
    expect(remove).toHaveBeenCalledWith(ITEMS[1]);
    document.body.innerHTML = "";

    const kept = list({ confirmRemove: () => false });
    await fireEvent.click(screen.getAllByRole("button", { name: "xRemove" })[0]!);
    expect(kept.remove).not.toHaveBeenCalled();
    expect(screen.getByText("iPhone")).toBeInTheDocument();
  });

  it("says what failed, and nothing when the person dismissed the device", async () => {
    list({ remove: async () => Promise.reject(new Error("not_found")) });
    await fireEvent.click(screen.getAllByRole("button", { name: "xRemove" })[0]!);
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: not_found");
    document.body.innerHTML = "";

    list({ authenticator: fakeAuthenticator({ register: async () => Promise.reject(named("AbortError")) }) });
    await fireEvent.click(screen.getByRole("button", { name: "+Add a passkey" }));
    await Promise.resolve();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    document.body.innerHTML = "";

    list({ registration: { options: async () => Promise.reject(new Error("passkey_expired")), add: vi.fn() } });
    await fireEvent.click(screen.getByRole("button", { name: "+Add a passkey" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("failed: passkey_expired");
  });

  it("says when there are none, and offers no button where the browser has no passkeys", () => {
    list({ passkeys: [], authenticator: fakeAuthenticator({ supported: () => false }) });
    expect(screen.getByRole("listitem")).toHaveTextContent("No passkeys yet.");
    expect(screen.queryByRole("button", { name: /Add a passkey/ })).not.toBeInTheDocument();
  });

  it("asks the browser by default", async () => {
    const ask = vi.spyOn(window, "prompt").mockReturnValue("Tablet");
    const confirming = vi.spyOn(window, "confirm").mockReturnValue(false);
    list({ ask: undefined, confirmRemove: undefined, addIcon: undefined, removeIcon: undefined });
    await fireEvent.click(screen.getByRole("button", { name: "Add a passkey" }));
    expect(await screen.findByText("Tablet")).toBeInTheDocument();
    await fireEvent.click(screen.getAllByRole("button", { name: "Remove" })[0]!);
    expect(confirming).toHaveBeenCalledWith("Remove this passkey?");
    expect(ask).toHaveBeenCalledWith("Name this passkey", expect.any(String));
    vi.restoreAllMocks();
  });
});

describe("alreadyAdded", () => {
  it("knows the server's code for a passkey on the account already", () => {
    expect(alreadyAdded(new ApiError(409, "passkey_exists"))).toBe(true);
    expect(alreadyAdded(new ApiError(400, "passkey_rejected"))).toBe(false);
    expect(alreadyAdded(new Error("passkey_exists"))).toBe(false);
    expect(alreadyAdded(null)).toBe(false);
  });
});

describe("passkeyMemory", () => {
  it("remembers a passkey used and an offer declined, under the application's prefix", () => {
    const storage = new MemoryStorage();
    const memory = passkeyMemory("myapp", storage);
    expect([memory.usedHere(), memory.offerDeclined()]).toEqual([false, false]);
    memory.rememberUsed();
    memory.declineOffer();
    expect([memory.usedHere(), memory.offerDeclined()]).toEqual([true, true]);
    expect(storage.getItem("myapp:passkey-used")).toBe("1");
    expect(storage.getItem("myapp:passkey-offer-declined")).toBe("1");
    expect(passkeyMemory("other", storage).usedHere()).toBe(false);
  });

  it("uses the browser's storage by default, and keeps nothing where it is refused", () => {
    passkeyMemory("myapp").rememberUsed();
    expect(localStorage.getItem("myapp:passkey-used")).toBe("1");
    localStorage.clear();
    const refused = passkeyMemory("myapp", new MemoryStorage(true));
    refused.rememberUsed();
    expect(refused.usedHere()).toBe(false);
  });
});
