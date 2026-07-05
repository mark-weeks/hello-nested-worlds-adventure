import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  test: {
    // Playwright owns e2e/*.spec.js; vitest must not try to run them.
    exclude: ["e2e/**", "node_modules/**"],
  },
  build: {
    outDir: "../static/app",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/world":  "http://localhost:8080",
      "/image":  "http://localhost:8080",
      "/speak":  "http://localhost:8080",
      "/puzzle": "http://localhost:8080",
      "/agent":  "http://localhost:8080",
      "/health": "http://localhost:8080",
      "/ws":     { target: "ws://localhost:8080", ws: true },
    },
  },
});
