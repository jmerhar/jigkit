// The interface: built into dist/, which the API serves beside /api. The shared app() preset hands
// /api to the API in the dev server (on its default port, or at VITE_API_TARGET: the dev stack's
// container name), targets the supported browsers and writes the bundled licences.
import { app } from "@jmerhar/frontend-config/vite";
import { test } from "@jmerhar/frontend-config/vitest";
import { paraglideVitePlugin } from "@inlang/paraglide-js";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";
import { mergeConfig } from "vite";
import { defineConfig } from "vitest/config";
import { paraglideOptions } from "./build/paraglide.ts";

export default mergeConfig(
  app(),
  defineConfig({
    // paraglideVitePlugin compiles messages/ into src/paraglide before each build and test run;
    // svelteTesting resolves Svelte's browser build under Vitest and cleans up after each test.
    plugins: [paraglideVitePlugin(paraglideOptions), svelte(), svelteTesting()],
    test: test({
      include: ["src/**/*.test.ts"],
      setupFiles: ["src/test-setup.ts"],
      coverage: {
        exclude: [
          "src/test-setup.ts",
          "src/testing.ts",
          "src/main.ts",
          "src/lib/api-types.ts",
          "src/paraglide/**",
        ],
      },
    }),
  }),
);
