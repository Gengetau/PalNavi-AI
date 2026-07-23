import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [vue()],
  build: {
    target: "es2022",
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost/",
      },
    },
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.spec.ts"],
    globals: false,
    clearMocks: true,
    restoreMocks: true,
    unstubGlobals: true,
    pool: "threads",
    fileParallelism: false,
    testTimeout: 2_000,
  },
});
