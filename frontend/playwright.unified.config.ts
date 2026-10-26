import {pythonServer} from './playwright.server'
import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'./e2e',testMatch:'unified.spec.ts',workers:1,retries:0,timeout:60000,outputDir:'./test-results/unified',reporter:[['list']],use:{baseURL:'http://127.0.0.1:5184',browserName:'chromium',headless:true,screenshot:'only-on-failure'},webServer:{command:pythonServer('unified_e2e_server.py'),url:'http://127.0.0.1:5184/api/v1/health',reuseExistingServer:false,timeout:30000}})
