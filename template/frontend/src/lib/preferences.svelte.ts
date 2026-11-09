/**
 * This browser's theme, shared by the account's menu and the account page, so a choice made in
 * one shows in the other at once.
 */
import { chosenTheme, type Theme } from "./theme";

export const preferences = $state<{ theme: Theme }>({ theme: chosenTheme() });
