# @jmerhar/jigkit

The browser half of [jigkit](https://github.com/jmerhar/jigkit): the parts every small
self-hosted web app's interface needs, written once and tested once. It is released under the
same version as the Python package, whose API it talks to.

```bash
npm install --save-exact @jmerhar/jigkit
```

Each module is its own entry point, framework-free, and imports nothing it does not use:

| Import | What it gives an interface |
|---|---|
| `@jmerhar/jigkit/storage` | `browserStorage`, `readStored`, `keepStored`, `readChoice`: local storage that never throws, for a private window or blocked site data |
| `@jmerhar/jigkit/theme` | `applyTheme` (`<html data-theme>` and the browser bar's `theme-color`), `chosenTheme` and `chooseTheme` under a storage key of the app's |
| `@jmerhar/jigkit/i18n` | `createLanguage(runtime, { storageKey, intl })` over the app's generated Paraglide runtime: the person's choice, else the browser's languages, else the base one; `match` |
| `@jmerhar/jigkit/i18n/build` | `paraglideOptions()`, for the Vite plugin and a compile script |
| `@jmerhar/jigkit/i18n/testing` | `catalogueProblems`, `placeholders`, `texts`: every catalogue matches the first, placeholders included, across a message's variants |
| `@jmerhar/jigkit/api` | `ApiClient` and `ApiError`: JSON or a form in, JSON out, the write-guard header on writes, every failure with its status and the server's code |
| `@jmerhar/jigkit/format` | euros and amounts typed either way (`parseAmount`), basis points as percentages, days, moments, calendar dates in a time zone, file sizes; the locale is always a parameter |
| `@jmerhar/jigkit/passkeys` | `browserAuthenticator` over `@simplewebauthn/browser` (an optional peer dependency), `dismissed`, `deviceName` |

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

ES modules with type declarations; the TypeScript sources ship alongside. Node 22 or newer for
tooling; browsers from 2023 on.

## License

MIT
