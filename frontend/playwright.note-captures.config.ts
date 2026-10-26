import {pythonServer} from './playwright.server'
import {defineConfig} from '@playwright/test'
// P3-B real HTTP/PDF.js/temporary SQLite; model responses are explicitly isolated Mock.
// Ports/data never point at the persistent 5177 or 5180 environments.
export default defineConfig({
 testDir:'./e2e',testMatch:/(?:ai-)?note-captures\.spec\.ts/,workers:1,retries:0,timeout:60000,
 outputDir:'./test-results/note-captures',reporter:[['list']],
 use:{baseURL:'http://127.0.0.1:5182',browserName:'chromium',headless:true,screenshot:'only-on-failure'},
 webServer:[
  {command:pythonServer('note_captures_e2e_server.py'),url:'http://127.0.0.1:8005/api/v1/health',reuseExistingServer:false,timeout:30000},
  {command:'npm run dev -- --host 127.0.0.1 --port 5182 --strictPort',env:{LITERA_API_PROXY:'http://127.0.0.1:8005',VITE_LITERA_PREVIEW_MOCK:'true',CI:'true'},url:'http://127.0.0.1:5182/login',reuseExistingServer:false},
 ],
})
