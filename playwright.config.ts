import { defineConfig, devices } from '@playwright/test'

// Browser end-to-end tests: a real Chromium against the real API on a fresh, migrated, seeded (SYNTHETIC) database.
//   npm run test:e2e
const env = (globalThis as { process?: { env: Record<string, string | undefined>; platform?: string } }).process
const python = env?.env.FORMLAW_PYTHON ?? (env?.platform === 'win32' ? 'backend\\.venv\\Scripts\\python.exe' : 'backend/.venv/bin/python')

export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5180', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    { command: `${python} scripts/e2e_server.py`, url: 'http://127.0.0.1:8010/api/v1/health', timeout: 180_000, reuseExistingServer: false },
    { command: 'npx vite --port 5180 --strictPort --host 127.0.0.1', url: 'http://127.0.0.1:5180', timeout: 120_000, reuseExistingServer: false,
      env: { VITE_PROXY_TARGET: 'http://127.0.0.1:8010' } },
  ],
})
