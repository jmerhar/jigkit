import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { applyTheme, chooseTheme, chosenTheme } from "../src/theme";
import { MemoryStorage } from "./helpers";

const KEY = "myapp:theme";

beforeEach(() => {
  document.head.innerHTML = `
    <style>
      :root { --bg: #ffffff; --paper: #fafafa; }
      :root[data-theme="dark"] { --bg: #111111; --paper: #222222; }
    </style>
    <meta name="theme-color" media="(prefers-color-scheme: light)" content="#f0f0f0" />
    <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#101010" />`;
});

afterEach(() => {
  delete document.documentElement.dataset.theme;
  localStorage.clear();
});

const bars = () =>
  [...document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')].map((tag) => tag.content);

describe("applyTheme", () => {
  it("sets the root's theme and colours every bar in the page's background", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(bars()).toEqual(["#111111", "#111111"]);

    applyTheme("light");
    expect(bars()).toEqual(["#ffffff", "#ffffff"]);
  });

  it("hands each bar its own colour back when following the device", () => {
    applyTheme("dark");
    applyTheme(null);
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(bars()).toEqual(["#f0f0f0", "#101010"]);
  });

  it("reads another property for the background when told to", () => {
    applyTheme("dark", { background: "--paper" });
    expect(bars()).toEqual(["#222222", "#222222"]);
  });

  it("keeps the bars' colours when the stylesheet has no background", () => {
    applyTheme("dark", { background: "--nothing" });
    expect(bars()).toEqual(["#f0f0f0", "#101010"]);
  });

  it("applies to another root", () => {
    const root = document.createElement("div");
    applyTheme("dark", { root });
    expect(root.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});

describe("choosing a theme", () => {
  it("keeps the choice on this browser and shows it", () => {
    const storage = new MemoryStorage();
    expect(chosenTheme(KEY, storage)).toBeNull();

    chooseTheme(KEY, "dark", storage);
    expect(chosenTheme(KEY, storage)).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");

    chooseTheme(KEY, null, storage);
    expect(chosenTheme(KEY, storage)).toBeNull();
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });

  it("uses the browser's storage by default, and ignores what is not a theme", () => {
    chooseTheme(KEY, "light");
    expect(localStorage.getItem(KEY)).toBe("light");
    expect(chosenTheme(KEY)).toBe("light");
    localStorage.setItem(KEY, "auto");
    expect(chosenTheme(KEY)).toBeNull();
  });

  it("still shows a theme the browser will not keep", () => {
    chooseTheme(KEY, "dark", new MemoryStorage(true));
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
