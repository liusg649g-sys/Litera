import {pythonServer} from './playwright.server'
import {defineConfig} from '@playwright/test'
export default defineConfig({testDir:'./e2e',testMatch:'user-models.spec.ts',workers:1,retries:0,timeout:60000,
 outputDir:'./test-results/user-models',reporter:[['list'],['junit',{outputFile:'test-results/user-models.xml'}]],
 use:{baseURL:'http://127.0.0.1:5184',browserName:'chromium',headless:true,screenshot:'only-on-failure'},
 webServer:[
 {command:pythonServer('user_models_e2e_server.py'),url:'http://127.0.0.1:8006/api/v1/health',reuseExistingServer:false,timeout:30000},
 {command:'npm run dev -- --host 127.0.0.1 --port 5184 --strictPort',env:{LITERA_API_PROXY:'http://127.0.0.1:8006',VITE_LITERA_PREVIEW_MOCK:'false',CI:'true'},url:'http://127.0.0.1:5184/login',reuseExistingServer:false}
 ]})
