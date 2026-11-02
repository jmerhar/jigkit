<!--
  @component
  Logging in with a password, or with a passkey: from a button, or picked from the login field's
  autofill suggestions while the form waits. A browser that has logged in with a passkey before is
  offered one first. Styled by the application through the classes it carries: `card narrow` on
  the form, `wide-button`, `secondary`, `link`, `muted or`, `other-login` and `actions`.
-->
<script lang="ts">
  import { onMount, type Snippet } from "svelte";
  import { browserAuthenticator, dismissed, type Authenticator, type PasskeyMemory } from "../../passkeys.js";
  import type { ErrorMessage, LoginLabels, PasskeyLogin } from "./types.js";

  interface Props {
    /** The application's name, above the form. */
    title: string;
    labels: LoginLabels;
    /** Logs in with a login and password; resolves once the person is logged in. */
    logIn: (login: string, password: string) => Promise<void>;
    /** The passkey half; without it the form offers passwords only. */
    passkeys?: PasskeyLogin;
    memory?: PasskeyMemory;
    authenticator?: Authenticator;
    errorMessage: ErrorMessage;
    /**
     * Called once logged in. `offerPasskey` is true after a password login on a device that could
     * make a passkey, where none was used here and the offer was not turned down.
     */
    onDone: (outcome: { offerPasskey: boolean }) => void;
    /** Shown in the passkey button, such as a fingerprint icon. */
    icon?: Snippet;
    /**
     * How long a passkey request waits in the autofill before it is renewed: inside the five
     * minutes the server keeps its challenge.
     */
    renewMs?: number;
  }

  let {
    title,
    labels,
    logIn,
    passkeys,
    memory,
    authenticator = browserAuthenticator,
    errorMessage,
    onDone,
    icon,
    renewMs = 240_000,
  }: Props = $props();

  const supported = $derived(passkeys !== undefined && authenticator.supported());
  const passkeyFirst = $derived(supported && (memory?.usedHere() ?? false));

  let login = $state("");
  let password = $state("");
  let busy = $state(false);
  let error = $state("");
  let autofill = false;
  let renew: ReturnType<typeof setTimeout> | undefined;
  let open = true;

  async function finishWithPasskey(answer: unknown): Promise<void> {
    await passkeys!.logIn(answer);
    memory?.rememberUsed();
    onDone({ offerPasskey: false });
  }

  /** Wait in the login field's autofill for the person to pick one of this site's passkeys. */
  async function listen(): Promise<void> {
    if (!autofill || !open) return;
    clearTimeout(renew);
    try {
      const options = await passkeys!.options();
      renew = setTimeout(() => {
        authenticator.cancel();
        listen();
      }, renewMs);
      const answer = await authenticator.authenticate(options, true);
      clearTimeout(renew);
      busy = true;
      await finishWithPasskey(answer);
    } catch (failure) {
      // Cancelled by the button, a renewal or leaving the page; anything else is worth saying.
      if (!dismissed(failure)) error = errorMessage(failure);
    } finally {
      busy = false;
    }
  }

  onMount(() => {
    if (supported) {
      authenticator.autofill().then(
        (available) => {
          autofill = available;
          listen();
        },
        () => undefined,
      );
    }
    return () => {
      open = false;
      clearTimeout(renew);
      if (autofill) authenticator.cancel();
    };
  });

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    error = "";
    try {
      await logIn(login, password);
      const offerPasskey =
        supported &&
        !(memory?.usedHere() ?? false) &&
        !(memory?.offerDeclined() ?? false) &&
        (await authenticator.builtIn().catch(() => false));
      onDone({ offerPasskey });
    } catch (failure) {
      error = errorMessage(failure);
    } finally {
      busy = false;
    }
  }

  async function withPasskey(): Promise<void> {
    clearTimeout(renew);
    if (autofill) authenticator.cancel();
    busy = true;
    error = "";
    try {
      const options = await passkeys!.options();
      await finishWithPasskey(await authenticator.authenticate(options));
    } catch (failure) {
      if (!dismissed(failure)) error = errorMessage(failure);
      busy = false;
      listen();
    }
  }
</script>

<form class="card narrow" onsubmit={submit}>
  <h1>{title}</h1>
  <h2>{labels.heading}</h2>
  {#if passkeyFirst}
    <button type="button" class="wide-button" disabled={busy} onclick={withPasskey}>
      {@render icon?.()}
      {labels.passkey}
    </button>
    <p class="muted or"><small>{labels.orPassword}</small></p>
  {/if}
  <label>
    {labels.login}
    <input
      bind:value={login}
      required
      autocomplete={supported ? "username webauthn" : "username"}
      autocapitalize="none"
    />
  </label>
  <label>{labels.password}<input type="password" bind:value={password} required autocomplete="current-password" /></label>
  {#if error}<p role="alert">{error}</p>{/if}
  <div class="actions">
    <button type="submit" class:secondary={passkeyFirst} disabled={busy}>{busy ? labels.submitting : labels.submit}</button>
  </div>
  {#if supported && !passkeyFirst}
    <p class="other-login">
      <button type="button" class="link" disabled={busy} onclick={withPasskey}>{labels.passkey}</button>
    </p>
  {/if}
</form>
