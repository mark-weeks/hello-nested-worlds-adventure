// Chromium loads both clients from the Python server so these tests exercise
// the committed bundle under the production Content Security Policy.
import { defineConfig } from "@playwright/test";

const PORT = 8199;
const PYTHON = process.env.ENFOLDED_PYTHON || "python";

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
    command: `${PYTHON} ../scripts/e2e_server.py ${PORT}`,
    url: `http://127.0.0.1:${PORT}/health`,
    reuseExistingServer: false,
    timeout: 30_000,
    env: {
      ...process.env,
      // Keep the E2E world hermetic: no background walkers or staged-hop
      // pump mutating state while assertions read it.
      NESTED_WORLDS_HEARTBEAT: "0",
      NESTED_WORLDS_CAUSAL_PUMP: "0",
      NESTED_WORLDS_DISABLE_AI: "1",
      NESTED_WORLDS_DISABLE_IMAGES: "1",
      // Every spec on this shared server arrives from 127.0.0.1, so
      // together they spend one player's read budget (120 GETs a minute).
      // smoke, wayback and wrap make about 130 between them and fail with
      // 429s whenever they land in the same minute. The limiter itself is
      // covered by the Python suite.
      NESTED_WORLDS_RATE_LIMIT_GET_PER_MIN: "600",
    },
  },
});
