<script lang="ts">
  import { LoginForm, PasskeyOffer, SetupForm } from "@jmerhar/jigkit/auth/svelte";
  import { browserAuthenticator, type Authenticator } from "@jmerhar/jigkit/passkeys";
  import { onMount } from "svelte";
  import { Api, ApiError, type Me } from "./lib/api";
  import { errorMessage } from "./lib/errors";
  import { chooseLanguage, chosenLanguage } from "./lib/language";
  import { memory } from "./lib/passkeys";
  import { m } from "./paraglide/messages.js";
  import type { Locale } from "./paraglide/runtime.js";
  import Account from "./pages/Account.svelte";
  import Notes from "./pages/Notes.svelte";

  let {
    api = new Api(),
    authenticator = browserAuthenticator,
    reload = () => location.reload(),
  }: { api?: Api; authenticator?: Authenticator; reload?: () => void } = $props();

  /** What the app is showing. */
  let stage = $state<"loading" | "setup" | "login" | "ready" | "error">("loading");
  let page = $state<"notes" | "account">("notes");
  /** Whether the navigation is unfolded, on a screen too narrow to show it all. */
  let menuOpen = $state(false);

  function show(next: "notes" | "account"): void {
    page = next;
    menuOpen = false;
  }
  let me = $state<Me | null>(null);
  let problem = $state("");
  let offerPasskey = $state(false);

  /**
   * Follow the language saved on the account when this browser has chosen none, or another:
   * Paraglide reads its messages once per page, so this reloads. Returns whether it did.
   */
  function followAccountLanguage(): boolean {
    const wanted = me?.language as Locale | null | undefined;
    if (!wanted || wanted === chosenLanguage()) return false;
    chooseLanguage(wanted, reload);
    return true;
  }

  async function start(): Promise<void> {
    try {
      if ((await api.setupState()).required) {
        stage = "setup";
        return;
      }
      me = await api.me();
      if (!followAccountLanguage()) stage = "ready";
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 401) stage = "login";
      else {
        problem = errorMessage(failure);
        stage = "error";
      }
    }
  }

  function loggedIn(): void {
    if (!followAccountLanguage()) {
      page = "notes";
      stage = "ready";
    }
  }

  async function logOut(): Promise<void> {
    await api.logOut().catch(() => undefined);
    me = null;
    offerPasskey = false;
    stage = "login";
  }

  onMount(start);
</script>

{#if stage === "loading"}
  <p class="muted centre">{m.loading()}</p>
{:else if stage === "error"}
  <p role="alert" class="centre">{m.start_failed({ reason: problem })}</p>
{:else if stage === "setup"}
  <SetupForm
    labels={{
      heading: m.setup_title(),
      intro: m.setup_intro(),
      name: m.field_name(),
      login: m.field_login(),
      password: m.field_password(),
      passwordHint: m.field_password_hint(),
      submit: m.setup_submit(),
      submitting: m.saving(),
    }}
    setUp={async (details) => {
      me = await api.setUp({ ...details, language: chosenLanguage() });
    }}
    {errorMessage}
    onDone={loggedIn}
  />
{:else if stage === "login"}
  <LoginForm
    title={m.app_name()}
    labels={{
      heading: m.login_title(),
      login: m.field_login(),
      password: m.field_password(),
      submit: m.login_submit(),
      submitting: m.logging_in(),
      passkey: m.login_passkey(),
      orPassword: m.login_or_password(),
    }}
    logIn={async (login, password) => {
      me = await api.logIn(login, password);
    }}
    passkeys={{
      options: () => api.passkeyLoginOptions(),
      logIn: async (answer) => {
        me = await api.passkeyLogIn(answer);
      },
    }}
    {memory}
    {authenticator}
    {errorMessage}
    onDone={(outcome) => {
      offerPasskey = outcome.offerPasskey;
      loggedIn();
    }}
  />
{:else if me}
  <header class="site-header" data-open={menuOpen || undefined}>
    <strong class="brand">{m.app_name()}</strong>
    <button
      type="button"
      class="secondary small menu-toggle"
      aria-expanded={menuOpen}
      onclick={() => (menuOpen = !menuOpen)}
    >
      {m.nav_menu()}
    </button>
    <nav class="site-nav">
      <button type="button" class="link" aria-current={page === "notes"} onclick={() => show("notes")}>
        {m.nav_notes()}
      </button>
      <button type="button" class="link" aria-current={page === "account"} onclick={() => show("account")}>
        {m.nav_account()}
      </button>
      <button type="button" class="link" onclick={logOut}>{m.log_out()}</button>
    </nav>
  </header>
  <main>
    <PasskeyOffer
      bind:open={offerPasskey}
      labels={{
        offer: m.passkey_offer(),
        done: m.passkey_offer_done(),
        accept: m.passkey_offer_accept(),
        later: m.passkey_offer_later(),
        close: m.close(),
      }}
      registration={{ options: () => api.passkeyOptions(), add: (label, credential) => api.addPasskey(label, credential) }}
      {memory}
      {authenticator}
      {errorMessage}
    />
    {#if page === "notes"}
      <Notes {api} />
    {:else}
      <Account {api} {authenticator} {reload} bind:me={me} />
    {/if}
  </main>
{/if}
