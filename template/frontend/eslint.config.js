// ESLint for the interface: the shared TypeScript, Svelte and Node presets from
// @jmerhar/frontend-config. src/paraglide is compiled from messages/ before each build and test.
import { base, node } from "@jmerhar/frontend-config/eslint";
import { svelte } from "@jmerhar/frontend-config/eslint/svelte";

export default [...base({ ignores: ["src/paraglide", "public"] }), ...svelte(), node(["build/**/*.ts"])];
