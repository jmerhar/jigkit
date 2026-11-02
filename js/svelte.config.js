// TypeScript in the components' <script lang="ts">, compiled away for svelte-package so the
// published components are plain JavaScript, and read the same way by svelte-check and Vitest.
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

export default { preprocess: vitePreprocess({ script: true }) };
