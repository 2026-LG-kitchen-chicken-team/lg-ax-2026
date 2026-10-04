import { defineConfig } from '@playwright/test';

// Browser E2E for the planning workspace (P2-WEB-004). Uses the locally installed Chrome by default so no browser
// download is needed; set PLAYWRIGHT_CHANNEL='' to use Playwright's bundled Chromium (e.g. in CI after `npx playwright install chromium`).
const channel = process.env.PLAYWRIGHT_CHANNEL ?? 'chrome';

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:5173',
    ...(channel ? { channel } : {}),
    acceptDownloads: true,
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npm run dev',
    url: 'http://127.0.0.1:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
