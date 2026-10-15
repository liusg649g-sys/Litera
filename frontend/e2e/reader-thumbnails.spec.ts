import { test, expect } from '@playwright/test'
import { openLibrary, upload, origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'

for (const dpr of [1, 2]) test(`thumbnail DPR${dpr}: real text/image resolution, lazy release, navigation and document replacement`, async ({ browser }) => {
  const context = await browser.newContext({ baseURL: origin, deviceScaleFactor: dpr, viewport: { width: 1366, height: 768 } })
  const page = await context.newPage()
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message))
  try {
    const token = await openLibrary(page)
    const doc = await (await upload(page.request, token, readerPdf('Clarity', 40, false, { detail: true }), 'Clarity.pdf')).json()
    const other = await (await upload(page.request, token, readerPdf('Replacement', 4), 'Replacement.pdf')).json()
    await page.goto(`/reader/${doc.id}`)
    await expect(page.locator('[data-page="1"]')).toHaveAttribute('data-status', '已渲染')
    await page.getByRole('button', { name: '展开文献导航', exact: true }).click()
    const first = page.getByRole('button', { name: '缩略图第 1 页', exact: true }).locator('canvas')
    await expect.poll(() => first.evaluate((c: HTMLCanvasElement) => c.width)).toBe(128 * dpr)
    const size = await first.evaluate((c: HTMLCanvasElement) => ({ w: c.width, h: c.height, cssW: c.getBoundingClientRect().width, cssH: c.getBoundingClientRect().height }))
    expect(size.cssW).toBe(128); expect(size.cssH).toBeCloseTo(128 * 792 / 612, 1)
    expect(size.h).toBe(Math.ceil(size.cssH * dpr))
    const rotated = page.getByRole('button', { name: '缩略图第 3 页', exact: true }).locator('canvas')
    await expect.poll(() => rotated.evaluate((c: HTMLCanvasElement) => c.width)).toBe(128*dpr)
    expect(await rotated.evaluate(c => c.getBoundingClientRect().height)).toBeCloseTo(128*580/740, 1)
    // Actual ink in the title, body and embedded checkerboard image.
    const ink = await first.evaluate((c: HTMLCanvasElement) => {
      const ctx = c.getContext('2d')!, scale = c.width / 612
      return [[40, 35, 250, 25], [40, 120, 250, 12], [40, 200, 180, 150]].map(([x,y,w,h]) => {
        const pixels = ctx.getImageData(Math.round(x!*scale), Math.round(y!*scale), Math.ceil(w!*scale), Math.ceil(h!*scale)).data
        return Array.from(pixels).filter((v,i) => i%4!==3 && v<200).length
      })
    })
    for (const count of ink) expect(count).toBeGreaterThan(0)
    await page.screenshot({ path: `test-results/thumbnail-dpr${dpr}.png` })
    const image = await first.evaluate((c: HTMLCanvasElement) => c.toDataURL())
    const separator = page.getByRole('separator', { name: '调整文献导航宽度' })
    await separator.focus(); await page.keyboard.press('ArrowRight')
    // Fixed 128px thumbnail remains cached when the surrounding panel grows.
    expect(await first.evaluate((c: HTMLCanvasElement) => c.toDataURL())).toBe(image)
    expect(await page.locator('.pdf-thumbnail canvas').evaluateAll(cs => cs.filter(c => (c as HTMLCanvasElement).width > 0).length)).toBeLessThan(12)
    await page.getByRole('button', { name: '缩略图第 20 页', exact: true }).click()
    await expect(page.locator('[data-page="20"]')).toHaveAttribute('data-status', '已渲染')
    await expect(page.getByRole('button', { name: '缩略图第 20 页', exact: true })).toHaveAttribute('aria-current', 'page')
    await expect.poll(() => first.evaluate((c: HTMLCanvasElement) => c.width)).toBe(0)
    await page.getByRole('button', { name: '大纲', exact: true }).click()
    await expect(page.locator('.pdf-thumbnail')).toHaveCount(0)
    await page.getByRole('button', { name: '缩略图', exact: true }).click()
    await page.getByRole('button', { name: '缩略图第 1 页', exact: true }).click()
    await expect.poll(() => first.evaluate((c: HTMLCanvasElement) => c.width)).toBe(128*dpr)
    // Replace the document while old thumbnails are being requested.
    await page.getByRole('button', { name: '缩略图第 35 页', exact: true }).scrollIntoViewIfNeeded()
    await page.getByRole('link', { name: '文献管理', exact: true }).click()
    await page.locator('tbody .document-title').filter({ hasText: 'Replacement' }).click()
    await expect(page).toHaveURL(`/reader/${other.id}`)
    await expect(page.locator('[data-page="1"]')).toHaveAttribute('data-status', '已渲染')
    await page.getByRole('button', { name: '展开文献导航', exact: true }).click()
    await expect(page.locator('.pdf-thumbnail')).toHaveCount(4)
    await expect.poll(() => first.evaluate((c: HTMLCanvasElement) => c.width)).toBe(128*dpr)
    expect(errors).toEqual([])
    console.log(`thumbnail DPR${dpr}`, JSON.stringify(size), 'title/body/image ink', ink)
  } finally { await context.close() }
})
