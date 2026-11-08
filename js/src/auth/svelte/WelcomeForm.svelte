<!--
  @component
  Choosing a password from an invitation or reset link: the account's login, shown so the person
  knows what to log in with, and the password twice. Styled by the application through
  `card narrow` on the form.
-->
<script lang="ts">
  import type { ErrorMessage, WelcomeLabels } from "./types.js";

  interface Props {
    labels: WelcomeLabels;
    /** The account's login. */
    login: string;
    /** Sets the password from the link, and logs the person in. */
    accept: (password: string) => Promise<void>;
    errorMessage: ErrorMessage;
    onDone: () => void;
    /** The shortest password the server accepts. */
    minPasswordLength?: number;
  }

  let { labels, login, accept, errorMessage, onDone, minPasswordLength = 10 }: Props = $props();

  let password = $state("");
  let repeat = $state("");
  let busy = $state(false);
  let error = $state("");

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    error = "";
    if (password !== repeat) {
      error = labels.mismatch;
      return;
    }
    busy = true;
    try {
      await accept(password);
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
  <label>{labels.login}<input value={login} readonly autocomplete="username" /></label>
  <label>
    {labels.password}
    <input type="password" bind:value={password} required minlength={minPasswordLength} autocomplete="new-password" />
    <small>{labels.passwordHint}</small>
  </label>
  <label>
    {labels.repeat}
    <input type="password" bind:value={repeat} required minlength={minPasswordLength} autocomplete="new-password" />
  </label>
  {#if error}<p role="alert">{error}</p>{/if}
  <button type="submit" disabled={busy}>{busy ? labels.submitting : labels.submit}</button>
</form>
