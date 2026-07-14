import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@vinami/ui": path.resolve(__dirname, "packages/ui/src/index.tsx"),
      "@vinami/api-client": path.resolve(__dirname, "packages/api-client/src/index.ts"),
      "@vinami/contracts": path.resolve(__dirname, "packages/contracts/src/index.ts"),
      "@vinami/test-utils": path.resolve(__dirname, "packages/test-utils/src/index.ts"),
      "@web": path.resolve(__dirname, "apps/web")
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./packages/test-utils/src/setup.ts"],
    include: ["apps/web/**/*.test.{ts,tsx}", "packages/**/*.test.{ts,tsx}", "tests/frontend/**/*.test.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary"],
      thresholds: { lines: 75, functions: 70, branches: 65, statements: 75 }
    }
  }
});
