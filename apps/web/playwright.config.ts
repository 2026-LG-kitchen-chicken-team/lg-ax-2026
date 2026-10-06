import { defineConfig } from '@playwright/test';

// Browser E2E for the planning workspace (P2-WEB-004). Uses the locally installed Chrome by default so no browser
// download is needed; set PLAYWRIGHT_CHANNEL='' to use Playwright's bundled Chromium (e.g. in CI after `npx playwright install chromium`).
const channel = process.env.PLAYWRIGHT_CHANNEL ?? 'chrome';
// LGAX_E2E_PORT starts a separate test Vite (e.g. 5183) so the user's own 5173 dev server is never reused. The private
// workspace server only accepts Origin 5173, so a non-5173 run suits read-only (GET) flows: browsers send no Origin on
// same-origin GETs. Default stays 5173.
const port = process.env.LGAX_E2E_PORT ?? '5173';

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    ...(channel ? { channel } : {}),
    acceptDownloads: true,
    viewport: { width: 1280, height: 900 },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: port === '5173' ? 'npm run dev' : `npx vite --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
