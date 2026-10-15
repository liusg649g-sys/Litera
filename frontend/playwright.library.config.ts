import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', testMatch: /(?:library|library-p2b|library-ux)\.spec\.ts/, workers: 1, retries: 0,
  outputDir: './test-results/library',
  use: { browserName: 'chromium', headless: true, baseURL: 'http://127.0.0.1:5175', screenshot: 'only-on-failure' },
  webServer: [
    { command: '..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\e2e_server.py',
      url: 'http://127.0.0.1:8001/api/v1/health', reuseExistingServer: false, timeout: 30000 },
    { command: 'npm run dev -- --host 127.0.0.1 --port 5175 --strictPort',
      env: { LITERA_API_PROXY: 'http://127.0.0.1:8001', CI: 'true' }, url: 'http://127.0.0.1:5175/login', reuseExistingServer: false },
  ],
})
