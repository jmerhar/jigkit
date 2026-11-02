import { afterEach, describe, expect, it } from "vitest";
import { applyTheme, chooseTheme, chosenTheme } from "./theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

describe("theme", () => {
  it("follows the device until one is chosen, and remembers the choice", () => {
    expect(chosenTheme()).toBe("auto");
    chooseTheme("dark");
    expect([chosenTheme(), document.documentElement.dataset.theme]).toEqual(["dark", "dark"]);
    chooseTheme("auto");
    expect([chosenTheme(), document.documentElement.dataset.theme]).toEqual(["auto", undefined]);
  });

  it("shows a theme without choosing it", () => {
    applyTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(chosenTheme()).toBe("auto");
    applyTheme("auto");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
