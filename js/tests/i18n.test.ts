import { afterEach, describe, expect, it, vi } from "vitest";
import { createLanguage, match, type ParaglideRuntime } from "../src/i18n";
import { paraglideOptions, STRATEGY } from "../src/i18n/build";
import { catalogueProblems, placeholders, texts } from "../src/i18n/testing";
import { MemoryStorage } from "./helpers";

type Locale = "en" | "pt-PT";

/** A stand-in for an application's generated Paraglide runtime. */
function runtime(current: Locale = "en") {
  const strategies = new Map<string, { getLocale: () => string | undefined; setLocale: (l: string) => void }>();
  let getLocale = () => current;
  const fake: ParaglideRuntime<Locale> & { strategies: typeof strategies } = {
    baseLocale: "en",
    locales: ["en", "pt-PT"],
    getLocale: () => getLocale(),
    overwriteGetLocale: (replacement) => {
      getLocale = replacement;
    },
    defineCustomClientStrategy: (name, handler) => {
      strategies.set(name, handler);
    },
    strategies,
  };
  return fake;
}

const KEY = "myapp-language";

afterEach(() => {
  localStorage.clear();
  document.documentElement.lang = "";
});

describe("match", () => {
  const available = ["en", "pt-PT"] as const;

  it.each([
    [["pt-PT"], "pt-PT"],
    [["PT-pt"], "pt-PT"],
    [["pt"], "pt-PT"],
    [["pt-BR", "en"], "pt-PT"],
    [["de-DE", "en-US"], "en"],
    [["de", "fr"], undefined],
    [[], undefined],
  ])("finds %j as %s", (wanted, expected) => {
    expect(match(wanted, available)).toBe(expected);
  });

  it("prefers a whole tag to a related one later in the list", () => {
    expect(match(["en-GB"], ["en-US", "en-GB"])).toBe("en-GB");
  });
});

describe("createLanguage", () => {
  it("defines the choice and the browser's languages as strategies", () => {
    const fake = runtime();
    const storage = new MemoryStorage();
    const language = createLanguage(fake, { storageKey: KEY });
    let wanted = ["pt-BR"];
    language.useStrategies(
      () => wanted,
      () => storage,
    );
    const choice = fake.strategies.get("custom-choice")!;
    const browser = fake.strategies.get("custom-browser")!;

    expect(choice.getLocale()).toBeUndefined();
    expect(browser.getLocale()).toBe("pt-PT");
    wanted = ["de"];
    expect(browser.getLocale()).toBeUndefined();

    storage.setItem(KEY, "pt-PT");
    expect(choice.getLocale()).toBe("pt-PT");
    // Paraglide writes what it resolved back into each strategy; neither keeps it.
    choice.setLocale("en");
    browser.setLocale("en");
    expect(storage.getItem(KEY)).toBe("pt-PT");
  });

  it("reads the browser's languages and storage by default", () => {
    const fake = runtime();
    createLanguage(fake, { storageKey: KEY }).useStrategies();
    vi.spyOn(navigator, "languages", "get").mockReturnValue(["pt"]);
    localStorage.setItem(KEY, "en");

    expect(fake.strategies.get("custom-browser")!.getLocale()).toBe("pt-PT");
    expect(fake.strategies.get("custom-choice")!.getLocale()).toBe("en");
    vi.restoreAllMocks();
  });

  it("copes with a browser that lists no languages", () => {
    const fake = runtime();
    createLanguage(fake, { storageKey: KEY }).useStrategies();
    vi.spyOn(navigator, "languages", "get").mockReturnValue(undefined as unknown as readonly string[]);

    expect(fake.strategies.get("custom-browser")!.getLocale()).toBeUndefined();
    vi.restoreAllMocks();
  });

  it("keeps a choice and reloads into it, or forgets it", () => {
    const storage = new MemoryStorage();
    const language = createLanguage(runtime(), { storageKey: KEY });
    const reload = vi.fn();

    language.choose("pt-PT", reload, storage);
    expect(language.chosen(storage)).toBe("pt-PT");
    language.choose(null, reload, storage);
    expect(language.chosen(storage)).toBeNull();
    expect(reload).toHaveBeenCalledTimes(2);
  });

  it("ignores a stored value that is not one of its languages", () => {
    localStorage.setItem(KEY, "de");
    expect(createLanguage(runtime(), { storageKey: KEY }).chosen()).toBeNull();
  });

  it("stays as it is when storage refuses the choice", () => {
    const reload = vi.fn();
    createLanguage(runtime(), { storageKey: KEY }).choose("pt-PT", reload, new MemoryStorage(true));
    expect(reload).not.toHaveBeenCalled();
  });

  it("keeps a choice in the browser's storage by default", () => {
    const reload = vi.fn();
    createLanguage(runtime(), { storageKey: KEY }).choose("pt-PT", reload);
    expect(localStorage.getItem(KEY)).toBe("pt-PT");
    expect(reload).toHaveBeenCalledOnce();
  });

  it("settles the language for the page's life and names it on the root", () => {
    const fake = runtime("pt-PT");
    const language = createLanguage(fake, { storageKey: KEY });

    expect(language.settle()).toBe("pt-PT");
    expect(document.documentElement.lang).toBe("pt-PT");
    expect(fake.getLocale()).toBe("pt-PT");

    const root = document.createElement("html");
    expect(language.settle(root)).toBe("pt-PT");
    expect(root.lang).toBe("pt-PT");
  });

  it("formats in each language's Intl locale, or its own tag", () => {
    const language = createLanguage(runtime("en"), { storageKey: KEY, intl: { en: "en-GB" } });

    expect(language.intlLocale()).toBe("en-GB");
    expect(language.intlLocale("pt-PT")).toBe("pt-PT");
    expect(createLanguage(runtime("en"), { storageKey: KEY }).intlLocale()).toBe("en");
  });
});

describe("paraglideOptions", () => {
  it("names the project, the runtime's directory and the strategies", () => {
    expect(paraglideOptions()).toEqual({
      project: "./project.inlang",
      outdir: "./src/paraglide",
      strategy: ["custom-choice", "custom-browser", "baseLocale"],
    });
    expect(paraglideOptions({ outdir: "./gen" }).outdir).toBe("./gen");
  });

  it("hands out its own copy of the strategies", () => {
    paraglideOptions().strategy.pop();
    expect(paraglideOptions().strategy).toEqual([...STRATEGY]);
  });
});

describe("catalogue checks", () => {
  it("lists a message's placeholders, sorted", () => {
    expect(placeholders("{b} of {a} on {a_2}")).toEqual(["a", "a_2", "b"]);
    expect(placeholders("none")).toEqual([]);
  });

  it("finds nothing wrong with matching catalogues", () => {
    expect(
      catalogueProblems({
        en: { $schema: "x", hello: "Hello {name}" },
        pt: { $schema: "y", hello: "Olá {name}" },
      }),
    ).toEqual([]);
    expect(catalogueProblems({})).toEqual([]);
  });

  it("names every mismatch, by language and key", () => {
    expect(
      catalogueProblems({
        en: { hello: "Hello {name}", bye: "Bye", count: "{n} items", odd: 3 },
        pt: { hello: "Olá {nome}", count: 5, extra: "Extra", odd: "x" },
      }),
    ).toEqual([
      "en: odd is not text",
      "pt: hello fills in {nome} where en fills in {name}",
      "pt: bye is missing",
      "pt: count is not text",
      "pt: extra is not in en",
    ]);
  });

  it("reads a message's variants", () => {
    const variants = [{ declarations: ["input n"], selectors: ["n"], match: { "n=1": "one {n}", "n=*": "{n} {unit}" } }];
    expect(texts("plain")).toEqual(["plain"]);
    expect(texts(variants)).toEqual(["one {n}", "{n} {unit}"]);
    expect(texts(5)).toBeNull();
    expect(texts([{ selectors: [] }])).toBeNull();
    expect(texts([null])).toBeNull();
    expect(texts([{ match: { a: 1 } }])).toBeNull();
  });

  it("compares the placeholders across all of a message's variants", () => {
    const en = { count: [{ match: { "n=1": "one item", "n=*": "{n} items" } }] };
    expect(catalogueProblems({ en, pt: { count: [{ match: { "n=*": "{n} itens" } }] } })).toEqual([]);
    expect(catalogueProblems({ en, pt: { count: "itens" } })).toEqual(["pt: count fills in {} where en fills in {n}"]);
    expect(catalogueProblems({ en, pt: { count: [{ match: 3 }] } })).toEqual(["pt: count is not text"]);
  });

  it("lets a translation leave placeholders out when told to, but never add one", () => {
    const en = { zone: "{city} time" };
    expect(catalogueProblems({ en, pt: { zone: "hora local" } }, { allowFewer: true })).toEqual([]);
    expect(catalogueProblems({ en, pt: { zone: "hora de {place}" } }, { allowFewer: true })).toEqual([
      "pt: zone fills in {place} where en fills in {city}",
    ]);
  });
});
