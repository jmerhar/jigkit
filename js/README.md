# @jmerhar/jigkit

The browser half of [jigkit](https://github.com/jmerhar/jigkit): the parts every small
self-hosted web app's interface needs, written once and tested once. It is released under the
same version as the Python package, whose API it talks to.

```bash
npm install --save-exact @jmerhar/jigkit
```

Each module is its own entry point and imports nothing it does not use; all but
`auth/svelte` and `nav/svelte` are framework-free:

| Import | What it gives an interface |
|---|---|
| `@jmerhar/jigkit/storage` | `browserStorage`, `readStored`, `keepStored`, `readChoice`: local storage that never throws, for a private window or blocked site data |
| `@jmerhar/jigkit/theme` | `applyTheme` (`<html data-theme>` and the browser bar's `theme-color`), `chosenTheme` and `chooseTheme` under a storage key of the app's |
| `@jmerhar/jigkit/i18n` | `createLanguage(runtime, { storageKey, intl })` over the app's generated Paraglide runtime: the person's choice, else the browser's languages, else the base one; `match` |
| `@jmerhar/jigkit/i18n/build` | `paraglideOptions()`, for the Vite plugin and a compile script |
| `@jmerhar/jigkit/i18n/testing` | `catalogueProblems`, `placeholders`, `texts`: every catalogue matches the first, placeholders included, across a message's variants |
| `@jmerhar/jigkit/api` | `ApiClient` and `ApiError`: JSON or a form in, JSON out, the write-guard header on writes, every failure with its status and the server's code |
| `@jmerhar/jigkit/format` | euros and amounts typed either way (`parseAmount`), basis points as percentages, days, moments, calendar dates in a time zone, file sizes; the locale is always a parameter |
| `@jmerhar/jigkit/passkeys` | `browserAuthenticator` over `@simplewebauthn/browser` (an optional peer dependency), `dismissed`, `deviceName`, `passkeyMemory` |
| `@jmerhar/jigkit/auth/svelte` | `LoginForm` (password, passkey button and autofill), `SetupForm`, `WelcomeForm` (a password chosen from an invitation or reset link), `PasskeyOffer`, `PasskeyList`: Svelte 5 components (an optional peer dependency) taking the app's words and API calls as props, styled by the app's own stylesheet |
| `@jmerhar/jigkit/nav/svelte` | `AppNav`: the brand, pages, drop-down menus and the account's menu (with switches such as the theme and language), as a top bar on a wide screen and a bottom tab bar with "More" on a phone; icons are components the app passes in, such as `@lucide/svelte`'s |
| `@jmerhar/jigkit/styles/base.css` | the shared stylesheet, imported first by the app's own: colour tokens for light and dark, form controls, buttons, cards, tables, alerts, tags, chips, tabs, figure tiles, and a header whose navigation has drop-down groups and folds behind a menu button |

```ts
import { createLanguage } from "@jmerhar/jigkit/i18n";
import * as runtime from "./paraglide/runtime.js";

export const language = createLanguage(runtime, { storageKey: "myapp-language", intl: { en: "en-GB" } });
language.useStrategies();
language.settle();
```

```ts
import { ApiClient, writeHeader } from "@jmerhar/jigkit/api";

class Api extends ApiClient {
  constructor() {
    super({ writeHeader: writeHeader("myapp") });
  }
  items = () => this.request<Item[]>("GET", "/items");
}
```

```svelte
<LoginForm
  title="My app"
  labels={{ heading: m.login_title(), login: m.field_login(), password: m.field_password(),
            submit: m.login_submit(), submitting: m.logging_in(), passkey: m.login_passkey(),
            orPassword: m.login_or_password() }}
  logIn={async (login, password) => { me = await api.logIn(login, password); }}
  passkeys={{ options: api.passkeyLoginOptions, logIn: async (answer) => { me = await api.passkeyLogIn(answer); } }}
  memory={passkeyMemory("myapp")}
  {errorMessage}
  onDone={({ offerPasskey }) => (offer = offerPasskey)}
/>
```

ES modules with type declarations; the TypeScript sources ship alongside. Node 22 or newer for
tooling; browsers from 2023 on.

## License

MIT
