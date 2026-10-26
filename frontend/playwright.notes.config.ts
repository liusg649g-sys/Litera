import {pythonServer} from './playwright.server'
import {defineConfig} from '@playwright/test'
// Real temporary SQLite/HTTP/PDF.js. No real model service or 5177 data.
export default defineConfig({
 testDir:'./e2e',testMatch:/notes\.spec\.ts/,workers:1,retries:0,timeout:60000,
 outputDir:'./test-results/notes',reporter:[['list']],
 use:{baseURL:'http://127.0.0.1:5175',browserName:'chromium',headless:true,screenshot:'only-on-failure'},
 webServer:[
  {command:pythonServer('e2e_server.py'),url:'http://127.0.0.1:8001/api/v1/health',reuseExistingServer:false,timeout:30000},
  {command:'npm run dev -- --host 127.0.0.1 --port 5175 --strictPort',env:{LITERA_API_PROXY:'http://127.0.0.1:8001',CI:'true'},url:'http://127.0.0.1:5175/login',reuseExistingServer:false},
 ],
})
