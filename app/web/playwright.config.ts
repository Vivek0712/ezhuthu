import { defineConfig, devices } from '@playwright/test';

// e2e runs against a production build in mock mode: MSW's service worker answers /api/* per contracts/restore-api.md.
// E2E_PORT picks another port when 4173 is busy (parallel worktrees).
const PORT = Number(process.env.E2E_PORT ?? 4173);
export default defineConfig({
  testDir: 'e2e',
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list']],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1366, height: 900 } } },
    { name: 'mobile', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: PORT === 4173 ? 'npm run build:mock && npm run preview:mock' : `npm run build:mock && npx vite preview --mode mock --outDir dist-mock --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
