<script lang="ts">
  import { LoginForm, PasskeyOffer, SetupForm } from "@jmerhar/jigkit/auth/svelte";
  import { AppNav, type NavSwitch } from "@jmerhar/jigkit/nav/svelte";
  import { browserAuthenticator, type Authenticator } from "@jmerhar/jigkit/passkeys";
  import CircleUser from "@lucide/svelte/icons/circle-user";
  import Ellipsis from "@lucide/svelte/icons/ellipsis";
  import Globe from "@lucide/svelte/icons/globe";
  import LogOut from "@lucide/svelte/icons/log-out";
  import Monitor from "@lucide/svelte/icons/monitor";
  import Moon from "@lucide/svelte/icons/moon";
  import StickyNote from "@lucide/svelte/icons/sticky-note";
  import Sun from "@lucide/svelte/icons/sun";
  import User from "@lucide/svelte/icons/user";
  import { onMount } from "svelte";
  import { Api, ApiError, type Me } from "./lib/api";
  import { errorMessage } from "./lib/errors";
  import { chooseLanguage, chosenLanguage } from "./lib/language";
  import { memory } from "./lib/passkeys";
  import { preferences } from "./lib/preferences.svelte";
  import { chooseTheme, type Theme } from "./lib/theme";
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
  /** The page shown, from the address: #/account, or the notes. */
  const pageOf = (hash: string) => (hash === "#/account" ? "account" : "notes");
  let page = $state<"notes" | "account">(pageOf(location.hash));
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
    if (!followAccountLanguage()) stage = "ready";
  }

  const switches = $derived<NavSwitch[]>([
    {
      label: m.field_theme(),
      value: preferences.theme,
      options: [
        { value: "auto", label: m.theme_auto(), icon: Monitor },
        { value: "light", label: m.theme_light(), icon: Sun },
        { value: "dark", label: m.theme_dark(), icon: Moon },
      ],
      onchange: (value) => {
        preferences.theme = value as Theme;
        chooseTheme(preferences.theme);
      },
    },
    {
      label: m.field_language(),
      value: me?.language ?? "",
      options: [
        { value: "", label: m.language_browser(), icon: Globe },
        { value: "en", label: "EN" },
        { value: "pt-PT", label: "PT" },
      ],
      onchange: (value) => void setLanguage(value),
    },
  ]);

  /** Keep a language chosen from the account's menu on the account, then show the page in it. */
  async function setLanguage(value: string): Promise<void> {
    if (!me || (me.language ?? "") === value) return;
    me = await api.updateAccount({ name: me.name, language: value || null });
    chooseLanguage((me.language as Locale | null) ?? null, reload);
  }

  async function logOut(): Promise<void> {
    await api.logOut().catch(() => undefined);
    me = null;
    offerPasskey = false;
    stage = "login";
  }

  onMount(() => {
    const follow = () => (page = pageOf(location.hash));
    addEventListener("hashchange", follow);
    void start();
    return () => removeEventListener("hashchange", follow);
  });
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
  <AppNav
    brand={m.app_name()}
    home="#/"
    pages={[{ label: m.nav_notes(), href: "#/", icon: StickyNote, current: page === "notes" }]}
    account={{
      name: me.name,
      icon: CircleUser,
      items: [{ label: m.nav_account(), href: "#/account", icon: User, current: page === "account" }],
      switches,
      logOut: { label: m.log_out(), icon: LogOut, onclick: () => void logOut() },
    }}
    labels={{ nav: m.nav_main(), more: m.nav_more(), moreIcon: Ellipsis }}
  />
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
