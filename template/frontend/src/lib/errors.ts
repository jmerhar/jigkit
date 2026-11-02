/** What to tell a person when a request fails, in their language. */

import { ApiError } from "./api";
import { m } from "../paraglide/messages.js";

/** The message for each of the API's refusal codes. */
const BY_CODE: Record<string, () => string> = {
  invalid_login: m.error_invalid_login,
  too_many_attempts: m.error_too_many_attempts,
  already_set_up: m.error_already_set_up,
  password_too_short: m.error_password_too_short,
  wrong_password: m.error_wrong_password,
  notifications_off: m.error_notifications_off,
  notification_failed: m.error_notification_failed,
  passkey_rejected: m.error_passkey_rejected,
  passkey_unknown: m.error_passkey_unknown,
  passkey_expired: m.error_passkey_expired,
  passkey_exists: m.error_passkey_exists,
  not_found: m.error_not_found,
  invalid: m.error_invalid,
};

/** A failure as a sentence: the API's code translated, an unreachable server, or the raw reason. */
export function errorMessage(failure: unknown): string {
  if (failure instanceof ApiError) {
    if (failure.status === 0) return m.error_unreachable();
    const known = BY_CODE[failure.message];
    if (known) return known();
  }
  return m.error_other({ reason: failure instanceof Error ? failure.message : String(failure) });
}
