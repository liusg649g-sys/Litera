import {test,expect} from '@playwright/test'
import {readFileSync} from 'node:fs'
import {openLibrary,upload} from './library-fixtures'
// Optional supplied real PDF; no network dependency or third-party PDF committed to the repo.
test('published research PDF through real upload/content, three views and text copying',async({page})=>{
  const token=await openLibrary(page),bytes=readFileSync(process.env.LITERA_READER_PAPER!)
  const response=await upload(page.request,token,bytes,'真实学术论文.pdf');expect(response.status()).toBe(201)
  const doc=await response.json();await page.reload();await page.locator('tbody .document-title').first().click()
  const first=page.locator('[data-page="1"]');await expect(first).toHaveAttribute('data-status','已渲染')
  await expect(first.locator('.textLayer')).toContainText('Trace-based Just-in-Time')
  const span=first.locator('.textLayer span').filter({hasText:'Trace-based Just-in-Time'}).first(),bounds=(await span.boundingBox())!
  await page.mouse.move(bounds.x+1,bounds.y+bounds.height/2);await page.mouse.down();await page.mouse.move(bounds.x+bounds.width-1,bounds.y+bounds.height/2,{steps:10});await page.mouse.up()
  expect(await page.evaluate(()=>getSelection()?.toString())).toContain('Trace-based')
  const select=page.locator('.reader-view-select')
  await select.click();await page.getByRole('option',{name:'单页切换',exact:true}).click()
  await page.getByLabel('当前页码',{exact:true}).fill('14');await page.getByLabel('当前页码',{exact:true}).press('Enter')
  await expect(page.locator('[data-page="14"]')).toHaveAttribute('data-status','已渲染')
  await select.click();await page.getByRole('option',{name:'双页并排',exact:true}).click()
  await expect(page.locator('.pdf-page')).toHaveCount(2)
  await expect(page.locator('[data-page="13"]')).toHaveAttribute('data-status','已渲染')
  expect(await(await page.request.get(`/api/v1/documents/${doc.id}/content?download=true`)).body()).toEqual(bytes)
  await page.screenshot({path:'test-results/reader/published-paper.png'})
})
