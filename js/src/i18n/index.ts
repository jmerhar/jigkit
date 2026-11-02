/**
 * The interface's language: the person's own choice, or else the first of the browser's languages
 * the interface has, or else its base language.
 *
 * Messages are compiled per application by Paraglide, so each application passes its own generated
 * runtime (`src/paraglide/runtime.js`) to {@link createLanguage}. The choice and the browser's
 * languages are two custom Paraglide strategies (`custom-choice`, `custom-browser`, listed in
 * `paraglideOptions` from `@jmerhar/jigkit/i18n/build`). Paraglide writes the first language it
 * resolves back into every strategy, so its built-in localStorage strategy would keep a language
 * read from the browser as though it had been chosen, and the page would stop following the
 * browser after its first visit. These strategies ignore that write: only `choose` keeps a choice.
 */

import { browserStorage, keepStored, readChoice } from "../storage.js";

/** What this module needs of an application's generated Paraglide runtime. */
export interface ParaglideRuntime<L extends string> {
  baseLocale: L;
  locales: readonly L[];
  getLocale(): L;
  overwriteGetLocale(getLocale: () => L): void;
  defineCustomClientStrategy(
    strategy: `custom-${string}`,
    handler: { getLocale: () => string | undefined; setLocale: (locale: L) => void },
  ): void;
}

export interface LanguageOptions<L extends string> {
  /** Where the person's choice is kept in the browser's storage. */
  storageKey: string;
  /**
   * The locale Intl formats dates and numbers in, per language, when it is not the language's own
   * tag: English as `en-GB`, say, for the day first and a 24-hour clock.
   */
  intl?: Partial<Record<L, string>>;
}

/** A language's choice, matching and formatting locale, bound to one application's runtime. */
export interface Language<L extends string> {
  /** Give Paraglide the two strategies: the choice in `storage`, then the browser's languages. */
  useStrategies(languages?: () => readonly string[], storage?: () => Storage | undefined): void;
  /** The person's own choice, or null when the interface follows the browser. */
  chosen(storage?: Storage | undefined): L | null;
  /**
   * Keep a choice, or forget it when `language` is null, then `reload` into it: Paraglide reads
   * its messages once per page. Storage that refuses leaves the page as it is, without reloading.
   */
  choose(language: L | null, reload: () => void, storage?: Storage | undefined): void;
  /**
   * Settle the language for as long as the page is open, set `<html lang>` to it, and return it.
   * Paraglide asks its strategies again on every message, so without this a choice made in
   * another tab would change this page's words while its `lang` stayed as it was.
   */
  settle(root?: HTMLElement): L;
  /** The locale Intl formats in for `language`, the current one by default. */
  intlLocale(language?: L): string;
}

/**
 * The first of `available` among `wanted`: by its whole tag, or by its first part, so "pt" and
 * "pt-BR" find a "pt-PT" there is. Paraglide's own preferredLanguage strategy matches a first part
 * only against a locale's whole tag, so "pt" would not find "pt-PT".
 */
export function match<L extends string>(wanted: readonly string[], available: readonly L[]): L | undefined {
  for (const tag of wanted) {
    const lower = tag.toLowerCase();
    const exact = available.find((locale) => locale.toLowerCase() === lower);
    if (exact) return exact;
    const first = lower.split("-")[0];
    const related = available.find((locale) => locale.toLowerCase().split("-")[0] === first);
    if (related) return related;
  }
  return undefined;
}

/** The interface's language, for an application's Paraglide `runtime`. */
export function createLanguage<L extends string>(
  runtime: ParaglideRuntime<L>,
  { storageKey, intl = {} }: LanguageOptions<L>,
): Language<L> {
  const chosen = (storage: Storage | undefined = browserStorage()): L | null =>
    readChoice(storageKey, runtime.locales, storage);
  return {
    useStrategies(languages = () => navigator.languages ?? [], storage = browserStorage) {
      runtime.defineCustomClientStrategy("custom-choice", {
        getLocale: () => chosen(storage()) ?? undefined,
        setLocale: () => {},
      });
      runtime.defineCustomClientStrategy("custom-browser", {
        getLocale: () => match(languages(), runtime.locales),
        setLocale: () => {},
      });
    },
    chosen,
    choose(language, reload, storage = browserStorage()) {
      if (keepStored(storageKey, language, storage)) reload();
    },
    settle(root = document.documentElement) {
      const language = runtime.getLocale();
      runtime.overwriteGetLocale(() => language);
      root.lang = language;
      return language;
    },
    intlLocale(language = runtime.getLocale()) {
      return intl[language] ?? language;
    },
  };
}
