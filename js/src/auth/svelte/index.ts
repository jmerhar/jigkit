/**
 * Svelte components for logging in (`svelte` is an optional peer dependency this entry point
 * needs): {@link LoginForm}, {@link SetupForm}, {@link WelcomeForm}, {@link PasskeyOffer} and
 * {@link PasskeyList}. They take the application's words and API calls as props, and carry class
 * names for the application's stylesheet rather than styles of their own.
 */

export { default as LoginForm } from "./LoginForm.svelte";
export { default as PasskeyList } from "./PasskeyList.svelte";
export { default as PasskeyOffer } from "./PasskeyOffer.svelte";
export { default as SetupForm } from "./SetupForm.svelte";
export { default as WelcomeForm } from "./WelcomeForm.svelte";
export * from "./types.js";
