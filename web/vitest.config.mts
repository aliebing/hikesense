import { defineConfig } from "vitest/config";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  // CSS is irrelevant in tests; an inline config keeps vite from loading the
  // Tailwind PostCSS plugin (e.g. for maplibre-gl.css imported by MapPanel).
  css: { postcss: {} },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
