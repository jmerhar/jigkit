/**
 * Passkeys in the browser: asking the device's authenticator to make one or to sign in with one,
 * against the options and answers of `jigkit.auth.passkeys` on the server.
 *
 * The browser's half of each ceremony is `@simplewebauthn/browser`'s, an optional peer dependency
 * this module needs; {@link Authenticator} gathers it in one replaceable object, so views can be
 * tested without a real authenticator.
 */

import {
  browserSupportsWebAuthn,
  browserSupportsWebAuthnAutofill,
  platformAuthenticatorIsAvailable,
  startAuthentication,
  startRegistration,
  WebAuthnAbortService,
  type PublicKeyCredentialCreationOptionsJSON,
  type PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/browser";

export interface Authenticator {
  /** Whether this browser can use passkeys at all. */
  supported(): boolean;
  /** Whether the browser can offer passkeys among the username field's autofill suggestions. */
  autofill(): Promise<boolean>;
  /** Whether the device itself can make a passkey: a fingerprint, face or screen-lock reader. */
  builtIn(): Promise<boolean>;
  /** Make a passkey from the server's registration options; resolves to the answer to send back. */
  register(options: Record<string, unknown>): Promise<unknown>;
  /**
   * Sign in with a passkey from the server's options; resolves to the answer to send back. With
   * `autofill`, the request waits quietly until the person picks a passkey from the username
   * field's suggestions.
   */
  authenticate(options: Record<string, unknown>, autofill?: boolean): Promise<unknown>;
  /** Stop a request that is waiting, which then rejects as an AbortError. */
  cancel(): void;
}

/** The browser's own authenticator. */
export const browserAuthenticator: Authenticator = {
  supported: browserSupportsWebAuthn,
  autofill: browserSupportsWebAuthnAutofill,
  builtIn: platformAuthenticatorIsAvailable,
  register: (options) =>
    startRegistration({ optionsJSON: options as unknown as PublicKeyCredentialCreationOptionsJSON }),
  authenticate: (options, autofill = false) =>
    startAuthentication({
      optionsJSON: options as unknown as PublicKeyCredentialRequestOptionsJSON,
      useBrowserAutofill: autofill,
    }),
  cancel: () => WebAuthnAbortService.cancelCeremony(),
};

/** Whether a ceremony failed because the person dismissed it, which needs no error message. */
export function dismissed(error: unknown): boolean {
  return error instanceof Error && (error.name === "NotAllowedError" || error.name === "AbortError");
}

const DEVICES: readonly (readonly [RegExp, string])[] = [
  [/iPhone/, "iPhone"],
  [/iPad/, "iPad"],
  [/Android/, "Android"],
  [/Macintosh|Mac OS X/, "Mac"],
  [/Windows/, "Windows"],
  [/Linux/, "Linux"],
];

/** A name for this device to label a passkey with, guessed from the browser: "iPhone", "Mac". */
export function deviceName(userAgent: string = navigator.userAgent, fallback = "Passkey"): string {
  return DEVICES.find(([pattern]) => pattern.test(userAgent))?.[1] ?? fallback;
}
