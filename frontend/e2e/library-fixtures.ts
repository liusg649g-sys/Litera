import { expect } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
export const origin = 'http://127.0.0.1:5175'
let account = 0
export function pdf(label = 'Litera PDF') {
  const objects = ['<< /Type /Catalog /Pages 2 0 R >>', '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 400] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
    `<< /Length ${label.length + 31} >>\nstream\nBT /F1 16 Tf 30 350 Td (${label}) Tj ET\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
  let value = '%PDF-1.4\n', offsets = [0]
  objects.forEach((object, index) => { offsets.push(Buffer.byteLength(value)); value += `${index + 1} 0 obj\n${object}\nendobj\n` })
  const xref = Buffer.byteLength(value)
  value += 'xref\n0 6\n0000000000 65535 f \n' + offsets.slice(1).map(offset => String(offset).padStart(10, '0') + ' 00000 n \n').join('')
  return Buffer.from(value + `trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`)
}
export async function session(request: APIRequestContext) {
  const email = `library-${Date.now()}-${++account}@example.com`
  expect((await request.post('/api/v1/auth/register', { headers: { Origin: origin }, data: { email, password: 'Litera-test-123', displayName: '文献测试用户' } })).status()).toBe(201)
  const login = await request.post('/api/v1/auth/login', { headers: { Origin: origin }, data: { email, password: 'Litera-test-123' } })
  expect(login.status()).toBe(200)
  return (await login.json()).csrfToken as string
}
export async function upload(request: APIRequestContext, token: string, bytes: Buffer, name = 'sample.pdf') {
  return request.post('/api/v1/documents', { headers: { Origin: origin, 'X-CSRF-Token': token }, multipart: { file: { name, mimeType: 'application/pdf', buffer: bytes } } })
}
export async function openLibrary(page: Page) {
  const token = await session(page.request)
  await page.goto('/library')
  await expect(page.getByRole('heading', { name: '我的文献', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: '导入 PDF', exact: true })).toBeEnabled()
  return token
}
export async function selectLibraryOption(page: Page, label: string, option: string) {
  await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: label, exact: true }) }).locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: option, exact: true }).click()
}
export async function setLibraryCheckbox(page: Page, name: string, checked = true) {
  const checkbox = page.getByRole('checkbox', { name, exact: true })
  if (await checkbox.isChecked() !== checked) await checkbox.locator('xpath=ancestor::label[1]').click()
  await expect(checkbox).toBeChecked({ checked })
}
