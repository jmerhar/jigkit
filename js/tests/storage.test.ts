import { afterEach, describe, expect, it, vi } from "vitest";
import { browserStorage, keepStored, readChoice, readStored } from "../src/storage";
import { MemoryStorage } from "./helpers";

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("browserStorage", () => {
  it("is the page's local storage", () => {
    expect(browserStorage()).toBe(window.localStorage);
  });

  it("is undefined where reading it is refused", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(browserStorage()).toBeUndefined();
  });
});

describe("reading and keeping values", () => {
  it("keeps, reads and forgets a value", () => {
    const storage = new MemoryStorage();
    expect(readStored("k", storage)).toBeNull();
    expect(keepStored("k", "v", storage)).toBe(true);
    expect(readStored("k", storage)).toBe("v");
    expect(keepStored("k", null, storage)).toBe(true);
    expect(readStored("k", storage)).toBeNull();
  });

  it("uses the browser's storage by default", () => {
    keepStored("k", "v");
    expect(localStorage.getItem("k")).toBe("v");
    expect(readStored("k")).toBe("v");
  });

  it("treats storage that refuses, or none at all, as empty and unwritable", () => {
    const refusing = new MemoryStorage(true);
    expect(readStored("k", refusing)).toBeNull();
    expect(keepStored("k", "v", refusing)).toBe(false);
    expect(keepStored("k", null, refusing)).toBe(false);
  });

  it("keeps nothing where the browser has no storage to give", () => {
    vi.spyOn(window, "localStorage", "get").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    expect(keepStored("k", "v")).toBe(false);
    expect(readStored("k")).toBeNull();
  });

  it("reads a choice only when it is one of those allowed", () => {
    const storage = new MemoryStorage();
    keepStored("size", "large", storage);
    expect(readChoice("size", ["small", "large"], storage)).toBe("large");
    expect(readChoice("size", ["small"], storage)).toBeNull();
    expect(readChoice("missing", ["small"], storage)).toBeNull();
  });
});
