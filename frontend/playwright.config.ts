import { defineConfig } from '@playwright/test'
const uiPort = process.env.LITERA_UI_PORT || '5174'
const uiOrigin = 'http://127.0.0.1:' + uiPort
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  outputDir: './test-results/auth',
  use: { browserName: 'chromium', headless: true, screenshot: 'only-on-failure' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port ' + uiPort + ' --strictPort',
    url: uiOrigin + '/login', reuseExistingServer: false,
  },
  projects: [
    { name: 'auth-integration', testMatch: /auth\.spec\.ts/,
      use: { baseURL: process.env.LITERA_URL || 'http://localhost:8080' } },
    { name: 'auth-ui', testMatch: /auth-ui\.spec\.ts/,
      use: { baseURL: uiOrigin } },
  ],
})
