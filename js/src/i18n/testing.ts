/**
 * Checks of an application's message catalogues, for its own test suite:
 *
 *     expect(catalogueProblems({ en, "pt-PT": pt })).toEqual([]);
 */

/** A catalogue as an inlang message-format file holds it: message keys to messages. */
export type Catalogue = Record<string, unknown>;

/** The placeholders a text fills in, such as `{version}`, sorted. */
export function placeholders(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map((found) => found[1] as string).sort();
}

/**
 * Every text a message can give: a plain string, or each variant of a message with variants (a
 * list of `{ match: { selector: text } }`); null for anything else.
 */
export function texts(message: unknown): string[] | null {
  if (typeof message === "string") return [message];
  if (!Array.isArray(message)) return null;
  const found: string[] = [];
  for (const part of message) {
    const match = (part as { match?: unknown } | null)?.match;
    if (!match || typeof match !== "object") return null;
    for (const text of Object.values(match)) {
      if (typeof text !== "string") return null;
      found.push(text);
    }
  }
  return found;
}

/** Whether a translation's placeholders are the original's, or some of them when fewer will do. */
function fits(translation: string[], original: string[], allowFewer: boolean): boolean {
  if (allowFewer) return translation.every((name) => original.includes(name));
  return translation.join() === original.join();
}

/** The placeholders any of a message's texts fill in, sorted and without repeats. */
function filled(message: string[]): string[] {
  return [...new Set(message.flatMap(placeholders))].sort();
}

export interface CatalogueOptions {
  /**
   * Let a translation leave out placeholders the first catalogue fills in, for a language whose
   * phrasing does better without one; it still may not fill in any other.
   */
  allowFewer?: boolean;
}

/**
 * Whatever keeps the catalogues from matching the first one: a message missing from a language or
 * found only there, a message that is neither text nor variants of text, or a translation filling
 * in other placeholders than the first catalogue's message does, across all its variants. The
 * `$schema` key is not a message. Each problem is one line, naming the language and the key.
 */
export function catalogueProblems(
  catalogues: Record<string, Catalogue>,
  { allowFewer = false }: CatalogueOptions = {},
): string[] {
  const [base, ...others] = Object.entries(catalogues);
  if (!base) return [];
  const [baseName, baseMessages] = base;
  const keys = (catalogue: Catalogue) => Object.keys(catalogue).filter((key) => key !== "$schema");
  const problems: string[] = [];
  for (const key of keys(baseMessages)) {
    if (!texts(baseMessages[key])) problems.push(`${baseName}: ${key} is not text`);
  }
  for (const [name, messages] of others) {
    for (const key of keys(baseMessages)) {
      if (!(key in messages)) {
        problems.push(`${name}: ${key} is missing`);
        continue;
      }
      const translation = texts(messages[key]);
      const original = texts(baseMessages[key]);
      if (!translation) problems.push(`${name}: ${key} is not text`);
      else if (original && !fits(filled(translation), filled(original), allowFewer)) {
        problems.push(
          `${name}: ${key} fills in {${filled(translation).join("}, {")}} where ${baseName} fills in {${filled(original).join("}, {")}}`,
        );
      }
    }
    for (const key of keys(messages)) {
      if (!(key in baseMessages)) problems.push(`${name}: ${key} is not in ${baseName}`);
    }
  }
  return problems;
}
