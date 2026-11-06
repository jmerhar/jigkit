// The suite runs in jsdom, for the modules that read the document, storage and navigator.
// svelteTesting resolves Svelte's browser build under Vitest and cleans up after each test.
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [svelte(), svelteTesting()],
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.ts"],
    setupFiles: ["tests/setup.ts"],
    // The base stylesheet is read as text by its test, which needs CSS processed rather than
    // replaced by an empty module.
    css: { include: [/styles\/base\.css/] },
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,svelte}"],
      // json-summary is what coverage.toml's shared tooling reads; lcov is Codecov's.
      reporter: ["text", "json-summary", "json", "lcov", ["html", { subdir: "html" }]],
      reportsDirectory: "coverage",
    },
  },
});
