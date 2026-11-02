import { beforeEach, describe, expect, it, vi } from "vitest";

const library = vi.hoisted(() => ({
  browserSupportsWebAuthn: vi.fn(() => true),
  browserSupportsWebAuthnAutofill: vi.fn(async () => true),
  platformAuthenticatorIsAvailable: vi.fn(async () => false),
  startRegistration: vi.fn(async () => ({ id: "made" })),
  startAuthentication: vi.fn(async () => ({ id: "signed" })),
  WebAuthnAbortService: { cancelCeremony: vi.fn() },
}));
vi.mock("@simplewebauthn/browser", () => library);

const { browserAuthenticator, deviceName, dismissed } = await import("../src/passkeys");

beforeEach(() => vi.clearAllMocks());

describe("browserAuthenticator", () => {
  it("asks the library what the browser and device can do", async () => {
    expect(browserAuthenticator.supported()).toBe(true);
    expect(await browserAuthenticator.autofill()).toBe(true);
    expect(await browserAuthenticator.builtIn()).toBe(false);
  });

  it("runs the ceremonies on the server's options", async () => {
    const options = { challenge: "abc" };

    expect(await browserAuthenticator.register(options)).toEqual({ id: "made" });
    expect(library.startRegistration).toHaveBeenCalledWith({ optionsJSON: options });
    expect(await browserAuthenticator.authenticate(options)).toEqual({ id: "signed" });
    expect(library.startAuthentication).toHaveBeenLastCalledWith({ optionsJSON: options, useBrowserAutofill: false });
    await browserAuthenticator.authenticate(options, true);
    expect(library.startAuthentication).toHaveBeenLastCalledWith({ optionsJSON: options, useBrowserAutofill: true });
  });

  it("cancels a waiting ceremony", () => {
    browserAuthenticator.cancel();
    expect(library.WebAuthnAbortService.cancelCeremony).toHaveBeenCalledOnce();
  });
});

describe("dismissed", () => {
  const named = (name: string) => Object.assign(new Error("x"), { name });

  it("tells a dismissed ceremony from a failed one", () => {
    expect(dismissed(named("NotAllowedError"))).toBe(true);
    expect(dismissed(named("AbortError"))).toBe(true);
    expect(dismissed(named("InvalidStateError"))).toBe(false);
    expect(dismissed("NotAllowedError")).toBe(false);
  });
});

describe("deviceName", () => {
  it.each([
    ["Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)", "iPhone"],
    ["Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X)", "iPad"],
    ["Mozilla/5.0 (Linux; Android 15; Pixel 9)", "Android"],
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 15_0)", "Mac"],
    ["Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Windows"],
    ["Mozilla/5.0 (X11; Linux x86_64)", "Linux"],
    ["Something else", "Passkey"],
  ])("names %s %s", (agent, name) => {
    expect(deviceName(agent)).toBe(name);
  });

  it("reads the browser's own agent, and takes another fallback", () => {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("Mozilla/5.0 (Windows NT 10.0)");
    expect(deviceName()).toBe("Windows");
    expect(deviceName("unknown", "Key")).toBe("Key");
    vi.restoreAllMocks();
  });
});
