// Browser E2E smoke: load both real clients from the real Python server —
// the committed/built bundle, the production CSP, an actual Chromium.
// This is the layer that would have caught the CSP-blocked-PixiJS blank
// scene that unit tests and vite dev-server checks structurally cannot see.
import { defineConfig } from "@playwright/test";

const PORT = 8199;

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    // The environment may pre-install Chromium outside the default cache
    // (PLAYWRIGHT_BROWSERS_PATH); an explicit executable overrides both.
    launchOptions: process.env.PW_CHROMIUM_PATH
      ? { executablePath: process.env.PW_CHROMIUM_PATH }
      : {},
  },
  webServer: {
    command: `python ../main.py serve --host 127.0.0.1 --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      ...process.env,
      // Keep the E2E world hermetic: no background walkers or staged-hop
      // pump mutating state while assertions read it.
      NESTED_WORLDS_HEARTBEAT: "0",
      NESTED_WORLDS_CAUSAL_PUMP: "0",
      HOME: process.env.E2E_HOME || process.env.HOME,
    },
  },
});
