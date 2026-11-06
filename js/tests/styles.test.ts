import { describe, expect, it } from "vitest";
import pkg from "../package.json";
import css from "../src/styles/base.css?raw";



/** The custom properties a block of rules sets, by name. */
function properties(block: string): string[] {
  return [...block.matchAll(/(--[\w-]+)\s*:/g)].map((match) => match[1]!).sort();
}

/** The body of the first rule whose selector is exactly `selector`. */
function rule(selector: string, from = 0): string {
  const start = css.indexOf(`${selector} {`, from);
  expect(start, selector).toBeGreaterThanOrEqual(0);
  return css.slice(start, css.indexOf("}", start));
}

describe("the base stylesheet", () => {
  it("is exported, and kept by bundlers", () => {
    expect(pkg.exports["./styles/base.css"]).toBe("./dist/styles/base.css");
    expect(pkg.sideEffects).toContain("**/*.css");
  });

  it("gives the dark themes every colour the light one has", () => {
    const light = properties(rule(":root"));
    const colours = light.filter((name) => !["--radius", "--control-radius", "--page-width"].includes(name));
    const darkDevice = properties(rule(':root:not([data-theme="light"])'));
    const darkChosen = properties(rule(':root[data-theme="dark"]'));

    expect(darkDevice).toEqual(colours);
    expect(darkChosen).toEqual(colours);
  });

  it("draws a select's arrow away from its edge instead of the native one", () => {
    const select = rule("select");

    expect(select).toContain("appearance: none");
    expect(select).toMatch(/padding-right: 2\.25rem/);
    expect(select).toMatch(/background-position:\s*right 1\.05rem center,\s*right 0\.75rem center/);
  });
});
