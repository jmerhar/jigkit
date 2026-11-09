import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { createRawSnippet, tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppNav, type NavAccount, type NavItem, type NavMenu } from "../src/nav/svelte";
import Icon from "./Icon.svelte";

const LABELS = { nav: "Main", more: "More", moreIcon: Icon };

const PAGES: NavItem[] = [
  { label: "Overview", href: "#/", icon: Icon, current: true },
  { label: "Bills", href: "#/bills", icon: Icon, badge: 2 },
  { label: "Income", href: "#/income", tab: false },
];

const MENUS: NavMenu[] = [
  { label: "Admin", icon: Icon, items: [{ label: "People", href: "#/people", badge: 1 }, { label: "Review", href: "#/review", badge: "" }] },
];

function nav(props: Record<string, unknown> = {}) {
  const logOut = vi.fn();
  const pick = vi.fn();
  const account: NavAccount = {
    name: "Ana",
    icon: Icon,
    items: [{ label: "Account", href: "#/account" }],
    switches: [
      {
        label: "Theme",
        value: "dark",
        options: [
          { value: "light", label: "Light", icon: Icon },
          { value: "dark", label: "Dark", icon: Icon },
        ],
        onchange: pick,
      },
      { label: "Language", value: "en", options: [{ value: "en", label: "EN" }, { value: "nl", label: "NL" }], onchange: pick },
    ],
    logOut: { label: "Log out", onclick: logOut },
  };
  render(AppNav, { brand: "My app", home: "#/", pages: PAGES, menus: MENUS, account, labels: LABELS, ...props });
  return { logOut, pick };
}

const button = (name: string) => screen.getByRole("button", { name: new RegExp(`^${name}`) });

describe("AppNav", () => {
  it("lists the pages with the current one marked, and keeps some off the phone's tab bar", () => {
    nav();

    const main = screen.getByRole("navigation", { name: "Main" });
    expect(screen.getByRole("link", { name: "My app" })).toHaveAttribute("href", "#/");
    expect(within(main).getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
    expect(within(main).getByRole("link", { name: "Bills 2" }).querySelector(".app-badge")).toHaveTextContent("2");
    expect(within(main).getByRole("link", { name: "Income" })).toHaveClass("app-wide-only");
    expect(within(main).getByRole("link", { name: "Bills 2" })).not.toHaveClass("app-wide-only");
  });

  it("opens one menu at a time, and closes it on Escape, outside, or once an entry is chosen", async () => {
    nav();

    await fireEvent.click(button("Admin"));
    expect(button("Admin")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "People 1" })).toBeInTheDocument();

    await fireEvent.click(button("Ana"));
    expect(button("Admin")).toHaveAttribute("aria-expanded", "false");
    expect(button("Ana")).toHaveAttribute("aria-expanded", "true");

    await fireEvent.keyDown(window, { key: "Escape" });
    expect(button("Ana")).toHaveAttribute("aria-expanded", "false");

    await fireEvent.click(button("Admin"));
    await fireEvent.click(screen.getByRole("link", { name: "My app" }));
    expect(button("Admin")).toHaveAttribute("aria-expanded", "false");

    await fireEvent.click(button("Admin"));
    await fireEvent.click(screen.getByRole("link", { name: "People 1" }));
    expect(screen.queryByRole("link", { name: "People 1" })).toBeNull();

    await fireEvent.click(button("Admin"));
    await fireEvent.click(button("Admin"));
    expect(screen.queryByRole("link", { name: "People 1" })).toBeNull();
  });

  it("puts what the tab bar has no room for under More, each menu as a section", async () => {
    nav();

    const more = button("More");
    expect(more).toHaveClass("marked");
    expect(more).not.toHaveClass("current");
    expect(button("Admin")).toHaveClass("marked");
    await fireEvent.click(more);
    const panel = document.getElementById(more.getAttribute("aria-controls")!)!;
    expect([...panel.querySelectorAll("li")].map((li) => li.textContent?.trim())).toEqual([
      "Income",
      "Admin",
      "People 1",
      "Review",
    ]);
    expect(panel.querySelector(".app-menu-heading")).toHaveTextContent("Admin");
  });

  it("marks a menu holding the current page, and leaves out More when everything has a tab", () => {
    nav({
      pages: [{ label: "Overview", href: "#/" }],
      menus: [{ label: "Admin", items: [{ label: "People", href: "#/people", current: true }] }],
    });
    expect(button("Admin")).toHaveClass("current");
    expect(button("Admin")).not.toHaveClass("marked");

    document.body.innerHTML = "";
    nav({ pages: [{ label: "Overview", href: "#/" }], menus: [] });
    expect(screen.queryByRole("button", { name: /^More/ })).toBeNull();
  });

  it("lists one menu's entries under More without a heading of its own", async () => {
    nav({ pages: [{ label: "Overview", href: "#/" }] });

    await fireEvent.click(button("More"));
    expect(document.querySelector(".app-menu-heading")).toBeNull();
    expect(screen.getByRole("link", { name: "People 1" })).toBeInTheDocument();
  });

  it("offers the account's entries, its switches and the way out", async () => {
    const { logOut, pick } = nav();

    await fireEvent.click(button("Ana"));
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "#/account");
    const theme = screen.getByRole("group", { name: "Theme" });
    expect(within(theme).getByRole("button", { name: "Dark" })).toHaveAttribute("aria-pressed", "true");
    expect(within(theme).getByRole("button", { name: "Light" })).toHaveAttribute("title", "Light");
    await fireEvent.click(within(theme).getByRole("button", { name: "Light" }));
    expect(pick).toHaveBeenCalledWith("light");
    const language = screen.getByRole("group", { name: "Language" });
    expect(within(language).getByRole("button", { name: "NL" })).not.toHaveAttribute("title");
    expect(button("Ana")).toHaveAttribute("aria-expanded", "true");

    await fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    expect(logOut).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Log out" })).toBeNull();
  });

  it("shows the application's tools, and works without an account or icons", () => {
    const tools = createRawSnippet(() => ({ render: () => `<input aria-label="Search" />` }));
    render(AppNav, {
      brand: "My app",
      home: "/",
      pages: [{ label: "Overview", href: "/" }],
      labels: { nav: "Main", more: "More" },
      tools,
    });

    expect(screen.getByLabelText("Search").closest(".app-tools")).toBeInTheDocument();
    expect(screen.queryByTestId("icon")).toBeNull();
  });

  it("closes nothing on a click outside when no menu is open, and keeps a menu open on a click in it", async () => {
    nav();
    await fireEvent.click(document.body);
    await fireEvent.click(button("Ana"));
    await fireEvent.click(screen.getByRole("group", { name: "Theme" }));
    expect(button("Ana")).toHaveAttribute("aria-expanded", "true");
  });

  it("draws a bare account menu, a button entry's icon, and More without an icon", async () => {
    render(AppNav, {
      brand: "My app",
      home: "/",
      pages: [
        { label: "Overview", href: "/", badge: "" },
        { label: "Income", href: "/income", tab: false },
      ],
      account: { name: "Bo" },
      labels: { nav: "Main", more: "More" },
    });

    expect(screen.getByRole("link", { name: "Overview" }).querySelector(".app-badge")).toBeNull();
    expect(button("More").querySelector("svg")).toBeNull();
    await fireEvent.click(button("Bo"));
    expect(document.getElementById(button("Bo").getAttribute("aria-controls")!)!.children).toHaveLength(0);
    expect(button("Bo")).not.toHaveClass("current");

    document.body.innerHTML = "";
    render(AppNav, {
      brand: "My app",
      home: "/",
      pages: [],
      account: { name: "Cy", items: [{ label: "Account", href: "/account", current: true }], logOut: { label: "Out", icon: Icon, onclick: () => {} } },
      labels: { nav: "Main", more: "More" },
    });
    expect(button("Cy")).toHaveClass("current");
    await fireEvent.click(button("Cy"));
    expect(screen.getByRole("button", { name: "Out" }).querySelector("svg")).not.toBeNull();
  });

  describe("fitting the bar", () => {
    let callback: (() => void) | undefined;
    const size = { scroll: 900, client: 800 };

    afterEach(() => {
      vi.unstubAllGlobals();
      vi.restoreAllMocks();
      callback = undefined;
    });

    function measured() {
      vi.stubGlobal(
        "ResizeObserver",
        class {
          constructor(fit: () => void) {
            callback = fit;
          }
          observe() {}
          disconnect() {}
        },
      );
      vi.spyOn(HTMLElement.prototype, "scrollWidth", "get").mockImplementation(() => size.scroll);
      vi.spyOn(HTMLElement.prototype, "clientWidth", "get").mockImplementation(() => size.client);
    }

    const bar = () => document.querySelector(".app-bar")!;

    it("moves the pages to the tab bar when the bar overflows, and back once there is room", async () => {
      measured();
      size.scroll = 900;
      size.client = 800;
      nav();
      await tick();
      await tick();
      expect(bar()).toHaveAttribute("data-compact");

      // Narrower than it needed: stays compact, whatever the tab bar now measures.
      size.scroll = 500;
      size.client = 850;
      callback!();
      await tick();
      expect(bar()).toHaveAttribute("data-compact");

      size.client = 900;
      callback!();
      await tick();
      expect(bar()).not.toHaveAttribute("data-compact");
    });

    it("stays one bar where everything fits", async () => {
      measured();
      size.scroll = 700;
      size.client = 800;
      nav();
      await tick();
      callback!();
      await tick();
      expect(bar()).not.toHaveAttribute("data-compact");
    });
  });
});
