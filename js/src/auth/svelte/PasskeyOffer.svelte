<!--
  @component
  After a password login on a device with a fingerprint, face or screen-lock reader: an offer to
  log in with it next time, set up in one tap instead of from the account page. Shown while `open`
  is true; turning it down is remembered on this browser. Styled through `note offer`, `actions`
  and `secondary`.
-->
<script lang="ts">
  import {
    browserAuthenticator,
    deviceName,
    dismissed,
    type Authenticator,
    type PasskeyMemory,
  } from "../../passkeys.js";
  import { alreadyAdded, type ErrorMessage, type PasskeyOfferLabels, type PasskeyRegistration } from "./types.js";

  interface Props {
    open: boolean;
    labels: PasskeyOfferLabels;
    registration: PasskeyRegistration;
    memory: PasskeyMemory;
    authenticator?: Authenticator;
    errorMessage: ErrorMessage;
    /** The new passkey's name, the device's by default. */
    label?: string;
  }

  let {
    open = $bindable(),
    labels,
    registration,
    memory,
    authenticator = browserAuthenticator,
    errorMessage,
    label = deviceName(),
  }: Props = $props();

  let busy = $state(false);
  let done = $state(false);
  let error = $state("");

  async function accept(): Promise<void> {
    busy = true;
    error = "";
    try {
      const options = await registration.options();
      await registration.add(label, await authenticator.register(options));
      memory.rememberUsed();
      done = true;
    } catch (failure) {
      if (alreadyAdded(failure)) {
        // This device has one already: nothing to offer.
        memory.rememberUsed();
        open = false;
      } else if (!dismissed(failure)) {
        error = errorMessage(failure);
      }
    } finally {
      busy = false;
    }
  }

  function later(): void {
    memory.declineOffer();
    open = false;
  }
</script>

{#if open}
  <div class="note offer" role="status">
    <p>{done ? labels.done : labels.offer}</p>
    {#if error}<p role="alert">{error}</p>{/if}
    <div class="actions">
      {#if done}
        <button type="button" class="secondary" onclick={() => (open = false)}>{labels.close}</button>
      {:else}
        <button type="button" disabled={busy} onclick={accept}>{labels.accept}</button>
        <button type="button" class="secondary" disabled={busy} onclick={later}>{labels.later}</button>
      {/if}
    </div>
  </div>
{/if}
