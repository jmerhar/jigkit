/**
 * How Paraglide compiles an application's messages, for its Vite plugin (builds, the dev server
 * and Vitest) and for a script that writes them for svelte-check, which runs no Vite:
 *
 *     // vite.config.ts
 *     paraglideVitePlugin(paraglideOptions())
 *     // build/compile-messages.ts
 *     await compile(paraglideOptions())
 *
 * The strategies are the ones `createLanguage` defines, then the base language.
 */

/** The strategies, in the order Paraglide tries them. */
export const STRATEGY = ["custom-choice", "custom-browser", "baseLocale"] as const;

export interface ParaglideOptions {
  project: string;
  outdir: string;
  strategy: ("custom-choice" | "custom-browser" | "baseLocale")[];
}

/** Paraglide's options: the inlang project and the generated runtime's directory, relative to the frontend. */
export function paraglideOptions({
  project = "./project.inlang",
  outdir = "./src/paraglide",
}: Partial<Pick<ParaglideOptions, "project" | "outdir">> = {}): ParaglideOptions {
  return { project, outdir, strategy: [...STRATEGY] };
}
