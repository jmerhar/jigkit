<!--
  @component
  The passkeys on the logged-in person's account, as the account page lists them: each with when
  it was last used and a button to remove it, and a button to add one where the browser can.
  Styled through `list`, `what`, `link` and `secondary`; the icons are the application's.
-->
<script lang="ts" generics="P extends PasskeyItem">
  import type { Snippet } from "svelte";
  import { browserAuthenticator, deviceName, dismissed, type Authenticator } from "../../passkeys.js";
  import type { ErrorMessage, PasskeyItem, PasskeyListLabels, PasskeyRegistration } from "./types.js";

  interface Props {
    passkeys: P[];
    labels: PasskeyListLabels;
    registration: PasskeyRegistration<P>;
    remove: (passkey: P) => Promise<void>;
    /** A moment as the application shows it. */
    formatWhen: (iso: string) => string;
    errorMessage: ErrorMessage;
    authenticator?: Authenticator;
    /** Asks for the new passkey's name, offering one; null keeps the offered name. */
    ask?: (question: string, offered: string) => string | null;
    /** Asks to confirm removing a passkey. */
    confirmRemove?: (question: string) => boolean;
    addIcon?: Snippet;
    removeIcon?: Snippet;
  }

  let {
    passkeys = $bindable(),
    labels,
    registration,
    remove,
    formatWhen,
    errorMessage,
    authenticator = browserAuthenticator,
    ask = (question, offered) => prompt(question, offered),
    confirmRemove = (question) => confirm(question),
    addIcon,
    removeIcon,
  }: Props = $props();

  let error = $state("");
  let notice = $state("");

  async function add(): Promise<void> {
    error = "";
    notice = "";
    try {
      const credential = await authenticator.register(await registration.options());
      const offered = deviceName();
      const label = ask(labels.labelPrompt, offered)?.trim() || offered;
      passkeys = [...passkeys, await registration.add(label, credential)];
      notice = labels.added;
    } catch (failure) {
      if (!dismissed(failure)) error = errorMessage(failure);
    }
  }

  async function removeOne(passkey: P): Promise<void> {
    if (!confirmRemove(labels.confirmRemove)) return;
    error = "";
    notice = "";
    try {
      await remove(passkey);
      passkeys = passkeys.filter((other) => other.id !== passkey.id);
    } catch (failure) {
      error = errorMessage(failure);
    }
  }
</script>

{#if error}<p role="alert">{error}</p>{/if}
{#if notice}<p role="status">{notice}</p>{/if}
<ul class="list">
  {#each passkeys as passkey (passkey.id)}
    <li>
      <span class="what">
        <strong>{passkey.label}</strong>
        <small>{passkey.last_used_at ? labels.lastUsed(formatWhen(passkey.last_used_at)) : labels.unused}</small>
      </span>
      <button type="button" class="link" onclick={() => removeOne(passkey)}>{@render removeIcon?.()}{labels.remove}</button>
    </li>
  {:else}
    <li class="muted">{labels.empty}</li>
  {/each}
</ul>
{#if authenticator.supported()}
  <button type="button" class="secondary" onclick={add}>{@render addIcon?.()}{labels.add}</button>
{/if}
