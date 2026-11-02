<script lang="ts">
  import { PasskeyList } from "@jmerhar/jigkit/auth/svelte";
  import type { Authenticator } from "@jmerhar/jigkit/passkeys";
  import { onMount } from "svelte";
  import type { Api, Me, Passkey } from "../lib/api";
  import { errorMessage } from "../lib/errors";
  import { moment } from "../lib/format";
  import { LANGUAGE_NAMES, chooseLanguage } from "../lib/language";
  import { chooseTheme, chosenTheme, type Theme } from "../lib/theme";
  import { m } from "../paraglide/messages.js";
  import { locales, type Locale } from "../paraglide/runtime.js";

  let {
    api,
    authenticator,
    reload,
    me = $bindable(),
  }: { api: Api; authenticator: Authenticator; reload: () => void; me: Me } = $props();

  // The form starts from the account as it is, and is the person's to change from there.
  // svelte-ignore state_referenced_locally
  let name = $state(me.name);
  // svelte-ignore state_referenced_locally
  let language = $state<string>(me.language ?? "");
  let theme = $state<Theme>(chosenTheme());
  let current = $state("");
  let next = $state("");
  let passkeys = $state<Passkey[]>([]);
  let error = $state("");
  let notice = $state("");

  function done(text: string): void {
    error = "";
    notice = text;
  }

  function failed(failure: unknown): void {
    notice = "";
    error = errorMessage(failure);
  }

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    try {
      const before = me.language;
      me = await api.updateAccount({ name, language: language || null });
      done(m.account_saved());
      if (me.language !== before) chooseLanguage((me.language as Locale | null) ?? null, reload);
    } catch (failure) {
      failed(failure);
    }
  }

  async function changePassword(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    try {
      await api.changePassword(current, next);
      current = next = "";
      done(m.password_changed());
    } catch (failure) {
      failed(failure);
    }
  }

  async function sendTest(): Promise<void> {
    try {
      await api.testNotification();
      done(m.notify_sent());
    } catch (failure) {
      failed(failure);
    }
  }

  onMount(async () => {
    try {
      passkeys = await api.passkeys();
    } catch (failure) {
      failed(failure);
    }
  });
</script>

<h1>{m.account_title()}</h1>
{#if error}<p role="alert">{error}</p>{/if}
{#if notice}<p role="status">{notice}</p>{/if}

<form class="card" onsubmit={save}>
  <label>{m.field_name()}<input bind:value={name} required maxlength="100" autocomplete="name" /></label>
  <label>
    {m.field_language()}
    <select bind:value={language}>
      <option value="">{m.language_browser()}</option>
      {#each locales as locale (locale)}<option value={locale}>{LANGUAGE_NAMES[locale]}</option>{/each}
    </select>
  </label>
  <label>
    {m.field_theme()}
    <select bind:value={theme} onchange={() => chooseTheme(theme)}>
      <option value="auto">{m.theme_auto()}</option>
      <option value="light">{m.theme_light()}</option>
      <option value="dark">{m.theme_dark()}</option>
    </select>
  </label>
  <div class="actions">
    <button type="submit">{m.save()}</button>
    {#if me.notifications}
      <button type="button" class="secondary" onclick={sendTest}>{m.notify_test()}</button>
    {/if}
  </div>
</form>

<h2>{m.password_title()}</h2>
<form class="card" onsubmit={changePassword}>
  <label>{m.password_current()}<input type="password" bind:value={current} required autocomplete="current-password" /></label>
  <label>
    {m.password_new()}<input type="password" bind:value={next} required minlength="10" autocomplete="new-password" />
    <small>{m.field_password_hint()}</small>
  </label>
  <div class="actions"><button type="submit">{m.password_submit()}</button></div>
</form>

<h2>{m.passkeys_title()}</h2>
<p class="muted">{m.passkeys_intro()}</p>
<PasskeyList
  bind:passkeys
  labels={{
    empty: m.passkeys_empty(),
    add: m.passkey_add(),
    remove: m.passkey_remove(),
    added: m.passkey_added(),
    unused: m.passkey_unused(),
    lastUsed: (when) => m.passkey_last_used({ when }),
    labelPrompt: m.passkey_label(),
    confirmRemove: m.confirm_remove_passkey(),
  }}
  registration={{ options: () => api.passkeyOptions(), add: (label, credential) => api.addPasskey(label, credential) }}
  remove={(passkey) => api.removePasskey(passkey.id)}
  formatWhen={moment}
  {errorMessage}
  {authenticator}
/>
