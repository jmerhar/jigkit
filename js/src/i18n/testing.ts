/**
 * Checks of an application's message catalogues, for its own test suite:
 *
 *     expect(catalogueProblems({ en, "pt-PT": pt })).toEqual([]);
 */

/** A catalogue as an inlang message-format file holds it: message keys to messages. */
export type Catalogue = Record<string, unknown>;

/** The placeholders a message fills in, such as `{version}`, sorted. */
export function placeholders(message: string): string[] {
  return [...message.matchAll(/\{(\w+)\}/g)].map((found) => found[1] as string).sort();
}

/**
 * Whatever keeps the catalogues from matching the first one: a message missing from a language or
 * found only there, a message that is not text, or a translation filling in other placeholders.
 * The `$schema` key is not a message. Each problem is one line, naming the language and the key.
 */
export function catalogueProblems(catalogues: Record<string, Catalogue>): string[] {
  const [base, ...others] = Object.entries(catalogues);
  if (!base) return [];
  const [baseName, baseMessages] = base;
  const keys = (catalogue: Catalogue) => Object.keys(catalogue).filter((key) => key !== "$schema");
  const problems: string[] = [];
  for (const key of keys(baseMessages)) {
    if (typeof baseMessages[key] !== "string") problems.push(`${baseName}: ${key} is not text`);
  }
  for (const [name, messages] of others) {
    for (const key of keys(baseMessages)) {
      if (!(key in messages)) {
        problems.push(`${name}: ${key} is missing`);
        continue;
      }
      const message = messages[key];
      const original = baseMessages[key];
      if (typeof message !== "string") problems.push(`${name}: ${key} is not text`);
      else if (typeof original === "string" && placeholders(message).join() !== placeholders(original).join()) {
        problems.push(
          `${name}: ${key} fills in {${placeholders(message).join("}, {")}} where ${baseName} fills in {${placeholders(original).join("}, {")}}`,
        );
      }
    }
    for (const key of keys(messages)) {
      if (!(key in baseMessages)) problems.push(`${name}: ${key} is not in ${baseName}`);
    }
  }
  return problems;
}
