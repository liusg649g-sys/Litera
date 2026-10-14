import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': process.env.LITERA_API_PROXY || 'http://localhost:8080' } },
  test: { environment: 'happy-dom', include: ['tests/**/*.test.ts'], restoreMocks: true },
})
