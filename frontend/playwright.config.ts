import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  use: { browserName: 'chromium', headless: true, screenshot: 'only-on-failure' },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174 --strictPort',
    url: 'http://127.0.0.1:5174/login', reuseExistingServer: false,
  },
  projects: [
    { name: 'auth-integration', testMatch: /auth\.spec\.ts/,
      use: { baseURL: process.env.LITERA_URL || 'http://localhost:8080' } },
    { name: 'auth-ui', testMatch: /auth-ui\.spec\.ts/,
      use: { baseURL: 'http://127.0.0.1:5174' } },
  ],
})
