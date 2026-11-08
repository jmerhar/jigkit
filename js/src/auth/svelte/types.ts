/**
 * What the login components need from an application: its words, in its own language, and the
 * calls to its API. The components hold no URLs and no messages of their own, so each application
 * keeps its API's shape and its catalogue.
 */

import type { ApiError } from "../../api.js";

/** The server's options for a passkey ceremony, as the browser's authenticator takes them. */
export type CeremonyOptions = Record<string, unknown>;

/** Turns a failed request into what to tell the person, in their language. */
export type ErrorMessage = (failure: unknown) => string;

export interface LoginLabels {
  heading: string;
  login: string;
  password: string;
  submit: string;
  submitting: string;
  /** The button that logs in with a passkey. */
  passkey: string;
  /** Between the passkey button and the password form, when a passkey is offered first. */
  orPassword: string;
}

/** The passkey half of a login, against `jigkit.auth.passkeys` on the server. */
export interface PasskeyLogin {
  options(): Promise<CeremonyOptions>;
  /** Sends the authenticator's answer; resolves once the person is logged in. */
  logIn(answer: unknown): Promise<void>;
}

export interface SetupLabels {
  heading: string;
  intro: string;
  name: string;
  login: string;
  password: string;
  passwordHint: string;
  submit: string;
  submitting: string;
}

/** The first account, as the setup form collects it. */
export interface SetupDetails {
  name: string;
  login: string;
  password: string;
}

export interface WelcomeLabels {
  heading: string;
  /** What the link is for, such as "Choose a password for your account, Ana." */
  intro: string;
  /** The login the account has, shown so the person knows what to log in with. */
  login: string;
  password: string;
  passwordHint: string;
  /** The password again. */
  repeat: string;
  /** Said when the two passwords differ. */
  mismatch: string;
  submit: string;
  submitting: string;
}

export interface PasskeyOfferLabels {
  offer: string;
  done: string;
  accept: string;
  later: string;
  close: string;
}

/** Adding a passkey to the logged-in person's account. */
export interface PasskeyRegistration<P = unknown> {
  options(): Promise<CeremonyOptions>;
  add(label: string, credential: unknown): Promise<P>;
}

/** A passkey as the account page lists it. */
export interface PasskeyItem {
  id: number | string;
  label: string;
  last_used_at: string | null;
}

export interface PasskeyListLabels {
  empty: string;
  add: string;
  remove: string;
  added: string;
  unused: string;
  /** When a passkey was last used, given the moment already formatted. */
  lastUsed(when: string): string;
  /** The prompt for a new passkey's name; the device's name is offered. */
  labelPrompt: string;
  confirmRemove: string;
}

/** Whether a failure is the server saying this device's passkey is on the account already. */
export function alreadyAdded(failure: unknown): boolean {
  return (failure as ApiError | null)?.name === "ApiError" && (failure as ApiError).message === "passkey_exists";
}
