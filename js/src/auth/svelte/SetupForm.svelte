<!--
  @component
  The first account, made on a new installation: a name, a login and a password, after any fields
  of the application's own (its `children`, bound to its own state). Styled by the application
  through `card narrow` on the form.
-->
<script lang="ts">
  import type { Snippet } from "svelte";
  import type { ErrorMessage, SetupDetails, SetupLabels } from "./types.js";

  interface Props {
    labels: SetupLabels;
    /** Creates the account and logs it in. */
    setUp: (details: SetupDetails) => Promise<void>;
    errorMessage: ErrorMessage;
    onDone: () => void;
    /** The shortest password the server accepts. */
    minPasswordLength?: number;
    /** The application's own fields, shown before the account's. */
    children?: Snippet;
  }

  let { labels, setUp, errorMessage, onDone, minPasswordLength = 10, children }: Props = $props();

  let name = $state("");
  let login = $state("");
  let password = $state("");
  let busy = $state(false);
  let error = $state("");

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    busy = true;
    error = "";
    try {
      await setUp({ name, login, password });
      onDone();
    } catch (failure) {
      error = errorMessage(failure);
    } finally {
      busy = false;
    }
  }
</script>

<form class="card narrow" onsubmit={submit}>
  <h1>{labels.heading}</h1>
  <p>{labels.intro}</p>
  {@render children?.()}
  <label>{labels.name}<input bind:value={name} required maxlength="100" autocomplete="name" /></label>
  <label>
    {labels.login}<input bind:value={login} required maxlength="100" autocomplete="username" autocapitalize="none" />
  </label>
  <label>
    {labels.password}
    <input type="password" bind:value={password} required minlength={minPasswordLength} autocomplete="new-password" />
    <small>{labels.passwordHint}</small>
  </label>
  {#if error}<p role="alert">{error}</p>{/if}
  <button type="submit" disabled={busy}>{busy ? labels.submitting : labels.submit}</button>
</form>
