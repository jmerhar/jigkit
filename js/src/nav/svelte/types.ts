import type { Component } from "svelte";

/** An icon component, such as one of `@lucide/svelte`'s, drawn in the colour of its text. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type NavIcon = Component<any>;

/** An entry in the navigation: a link, or a button that runs `onclick` (such as logging out). */
export interface NavItem {
  label: string;
  href?: string;
  onclick?: () => void;
  icon?: NavIcon;
  /** Whether this is the page shown; the application's router decides. */
  current?: boolean;
  /** A count or short mark beside the label, such as the number of items waiting. */
  badge?: string | number;
  /** False keeps a page off the phone's tab bar; it is listed under "More" there instead. */
  tab?: boolean;
}

/** Entries under one name: a drop-down menu on a wide screen, a section of "More" on a phone. */
export interface NavMenu {
  label: string;
  icon?: NavIcon;
  items: NavItem[];
}

/** A choice of one of a few values, such as the theme or the language, as a row of buttons. */
export interface NavSwitch {
  label: string;
  value: string;
  options: { value: string; label: string; icon?: NavIcon }[];
  onchange: (value: string) => void;
}

/** The account's menu: whose it is, its entries, its switches, and the way out. */
export interface NavAccount {
  name: string;
  icon?: NavIcon;
  items?: NavItem[];
  switches?: NavSwitch[];
  logOut?: NavItem;
}

/** The navigation's own words. */
export interface NavLabels {
  /** The navigation's accessible name. */
  nav: string;
  /** The phone's tab for everything the tab bar has no room for. */
  more: string;
  moreIcon?: NavIcon;
}
