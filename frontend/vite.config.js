import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
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
