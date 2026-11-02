/**
 * Light or dark: a theme the person chose on this browser, or the device's own setting.
 *
 * The stylesheet keys its colours on `<html data-theme>`, with the device's setting
 * (`prefers-color-scheme`) as the fallback when the attribute is absent. The browser's bar is
 * coloured by `<meta name="theme-color">` tags, one per scheme in index.html; a chosen theme gives
 * them all the page's background, and the device's setting hands each its own colour back.
 */

import { browserStorage, keepStored, readChoice } from "./storage.js";

/** The theme the page shows; null leaves it to the device. */
export type Theme = "light" | "dark" | null;

/** The themes a person can choose; choosing neither follows the device. */
export const THEMES: readonly ("light" | "dark")[] = ["light", "dark"];

/** Where a theme is shown, and the CSS custom property holding the page's background. */
export interface ThemeTarget {
  root?: HTMLElement;
  background?: string;
}

/**
 * Show a theme: `data-theme` on the root element, and the browser's bar in the page's background,
 * read from the stylesheet's `background` property (default `--bg`) once the theme applies. Null
 * hands both back to the device: each theme-color tag gets back the colour index.html gave it,
 * which is kept on the tag (`data-scheme`) the first time it is overridden.
 */
export function applyTheme(theme: Theme, { root = document.documentElement, background = "--bg" }: ThemeTarget = {}): void {
  if (theme) root.dataset.theme = theme;
  else delete root.dataset.theme;
  const colour = theme ? getComputedStyle(root).getPropertyValue(background).trim() : "";
  for (const tag of root.ownerDocument.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    if (tag.dataset.scheme === undefined) tag.dataset.scheme = tag.content;
    tag.content = colour || tag.dataset.scheme;
  }
}

/** The theme chosen on this browser under `key`, or null to follow the device. */
export function chosenTheme(key: string, storage: Storage | undefined = browserStorage()): Theme {
  return readChoice(key, THEMES, storage);
}

/**
 * Choose a theme on this browser under `key`, or null to follow the device, and show it. A
 * browser that keeps nothing shows the theme until the page is reloaded.
 */
export function chooseTheme(
  key: string,
  theme: Theme,
  storage: Storage | undefined = browserStorage(),
  target: ThemeTarget = {},
): void {
  keepStored(key, theme, storage);
  applyTheme(theme, target);
}
