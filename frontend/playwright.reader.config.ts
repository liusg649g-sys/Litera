import { defineConfig } from '@playwright/test'
const production = process.env.LITERA_READER_PRODUCTION === '1'
export default defineConfig({
  testDir: './e2e', testMatch: process.env.LITERA_READER_PAPER ? /reader-paper\.spec\.ts/ : /reader(?:-ux|-a2|-layout|-thumbnails)?\.spec\.ts/, workers: 1, retries: 0, timeout: 45000,
  outputDir: './test-results/reader',
  use: { browserName: 'chromium', headless: true, baseURL: 'http://127.0.0.1:5175', viewport: { width:1366,height:768 }, screenshot: 'only-on-failure' },
  webServer: [
    { command: '..\\backend\\.venv\\Scripts\\python.exe ..\\scripts\\e2e_server.py', url:'http://127.0.0.1:8001/api/v1/health', reuseExistingServer:false, timeout:30000 },
    { command: production ? 'npm run preview -- --host 127.0.0.1 --port 5175 --strictPort' : 'npm run dev -- --host 127.0.0.1 --port 5175 --strictPort', env:{LITERA_API_PROXY:'http://127.0.0.1:8001', CI:'true'}, url:'http://127.0.0.1:5175/login', reuseExistingServer:false },
  ],
})
