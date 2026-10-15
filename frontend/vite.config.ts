import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const pdfRoot = dirname(require.resolve('pdfjs-dist/package.json'))
const pdfVersion = JSON.parse(readFileSync(resolve(pdfRoot, 'package.json'), 'utf8')).version
const resources = ['cmaps', 'standard_fonts', 'wasm', 'iccs']
// Serve the installed package in dev and emit the same resources in production.
// No checked-in generated resources and no CDN dependencies.
function pdfResources(): import('vite').Plugin {
  const prefix = `/pdfjs/${pdfVersion}/`
  return {
    name: 'litera-pdf-resources',
    configureServer(server: import('vite').ViteDevServer) {
      server.middlewares.use((req, res, next) => {
        if (!req.url?.startsWith(prefix)) return next()
        const parts = req.url.slice(prefix.length).split('?')[0]!.split('/')
        if (parts.length !== 2 || !resources.includes(parts[0]!) || !/^[\w.-]+$/.test(parts[1]!)) {
          res.statusCode = 404; res.end(); return
        }
        try {
          const file = readFileSync(resolve(pdfRoot, parts[0]!, parts[1]!))
          res.setHeader('Content-Type', parts[1]!.endsWith('.wasm') ? 'application/wasm' : 'application/octet-stream')
          res.end(file)
        } catch { res.statusCode = 404; res.end() }
      })
    },
    generateBundle() {
      for (const directory of resources) for (const file of readdirSync(resolve(pdfRoot, directory))) {
        this.emitFile({ type: 'asset', fileName: `pdfjs/${pdfVersion}/${directory}/${file}`, source: readFileSync(resolve(pdfRoot, directory, file)) })
      }
    },
  }
}
export default defineConfig({
  plugins: [vue(), pdfResources()],
  server: { proxy: { '/api': process.env.LITERA_API_PROXY || 'http://localhost:8080' } },
  preview: { proxy: { '/api': process.env.LITERA_API_PROXY || 'http://localhost:8080' } },
  test: { environment: 'happy-dom', include: ['tests/**/*.test.ts'], restoreMocks: true },
})
