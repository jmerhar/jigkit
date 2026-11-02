/** Stand-ins for the login component tests. */

import { vi } from "vitest";
import type { Authenticator } from "../src/passkeys";
import type { LoginLabels, PasskeyListLabels, PasskeyOfferLabels, SetupLabels } from "../src/auth/svelte";

export const LOGIN: LoginLabels = {
  heading: "Log in",
  login: "Username",
  password: "Password",
  submit: "Log in",
  submitting: "Logging in…",
  passkey: "Log in with a passkey",
  orPassword: "or with your password",
};

export const SETUP: SetupLabels = {
  heading: "Set up",
  intro: "Make the first account.",
  name: "Name",
  login: "Username",
  password: "Password",
  passwordHint: "At least 10 characters",
  submit: "Create",
  submitting: "Saving…",
};

export const OFFER: PasskeyOfferLabels = {
  offer: "Log in with your fingerprint next time?",
  done: "Done: next time, use your fingerprint.",
  accept: "Set it up",
  later: "Not now",
  close: "Close",
};

export const LIST: PasskeyListLabels = {
  empty: "No passkeys yet.",
  add: "Add a passkey",
  remove: "Remove",
  added: "Passkey added.",
  unused: "Never used",
  lastUsed: (when) => `Last used ${when}`,
  labelPrompt: "Name this passkey",
  confirmRemove: "Remove this passkey?",
};

export const errorMessage = (failure: unknown) => `failed: ${(failure as Error).message}`;

export const named = (name: string) => Object.assign(new Error(name), { name });

/** An authenticator that answers at once, with the given abilities. */
export function fakeAuthenticator(overrides: Partial<Authenticator> = {}): Authenticator {
  return {
    supported: () => true,
    autofill: async () => false,
    builtIn: async () => true,
    register: vi.fn(async () => ({ made: true })),
    authenticate: vi.fn(async () => ({ pressed: true })),
    cancel: vi.fn(),
    ...overrides,
  };
}

/** An authenticator whose autofill request waits until `pick` answers it or `cancel` stops it. */
export function autofilling() {
  let answer: ((value: unknown) => void) | undefined;
  let stop: ((error: Error) => void) | undefined;
  const requests: boolean[] = [];
  const authenticator = fakeAuthenticator({
    autofill: async () => true,
    authenticate: (_options, autofill = false) => {
      requests.push(autofill);
      if (!autofill) return Promise.resolve({ pressed: true });
      return new Promise((resolve, reject) => {
        answer = resolve;
        stop = reject;
      });
    },
    cancel: vi.fn(() => stop?.(named("AbortError"))),
  });
  return { authenticator, requests, pick: (value: unknown) => answer?.(value) };
}
