import { test, expect } from '@playwright/test'
import { openLibrary, upload } from './library-fixtures'
import { readerPdf } from './reader-fixtures'

for (const width of [1440, 1024, 768]) {
  test(`reader panel toggles preserve independent panels at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    const token = await openLibrary(page)
    const response = await upload(page.request, token, readerPdf('Panel interaction'), 'Panels.pdf')
    const document = await response.json()
    await page.goto(`/reader/${document.id}`)
    await expect(page.locator('[data-page="1"]')).toHaveAttribute('data-status', '已渲染')
    for (const [name, selector] of [
      ['搜索文献', '.pdf-search'], ['批注列表', '.annotation-list'],
      ['翻译所选文字', '.translation-panel'], ['笔记面板', '.notes-panel'],
    ]) {
      const button = page.getByRole('button', { name, exact: true })
      await button.click()
      await expect(page.locator(selector)).toBeVisible()
      await button.click()
      await expect(page.locator(selector)).not.toBeVisible()
      await button.click()
      await expect(page.locator(selector)).toBeVisible()
      await button.click()
    }
    await page.getByRole('button', { name: '翻译所选文字', exact: true }).click()
    await page.getByRole('button', { name: '笔记面板', exact: true }).click()
    await expect(page.locator('.translation-panel')).toBeVisible()
    await expect(page.locator('.notes-panel')).toBeVisible()
    await page.getByRole('button', { name: '面板', exact: true }).click()
    await expect(page.locator('.translation-panel')).not.toBeVisible()
    await expect(page.locator('.notes-panel')).not.toBeVisible()
    await page.getByRole('button', { name: '面板', exact: true }).click()
    await expect(page.locator('.translation-panel')).toBeVisible()
    await expect(page.locator('.notes-panel')).toBeVisible()
  })
}
