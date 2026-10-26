import {test,expect} from '@playwright/test'
import {openLibrary,upload} from './library-fixtures'
import {readerPdf} from './reader-fixtures'

test('physical PDF line breaks retain raw text and expose separate normalized model input (Mock model)',async({page})=>{
  const token=await openLibrary(page)
  const doc=await(await upload(page.request,token,readerPdf('Line evidence sample',1,false,{lines:['disor-','ders and thera-','pies with ul-','trasound. high-intensity label-free','unknown-','word remains.']}),'line-evidence.pdf')).json()
  await page.goto(`/reader/${doc.id}`)
  await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染')
  const raw=await page.evaluate(()=>{
    const spans=[...document.querySelectorAll('.pdf-page[data-page="1"] .textLayer span')]
    const first=spans.find(el=>el.textContent==='disor-')!.firstChild!
    const last=spans.at(-1)!.firstChild!
    const range=document.createRange();range.setStart(first,0);range.setEnd(last,last.textContent!.length)
    window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)
    return window.getSelection()!.toString()
  })
  expect(raw).toContain('disor-')
  let submitted=''
  await page.route('**/api/v1/documents/*/translations',async route=>{
    const body=route.request().postDataJSON();submitted=body.text
    expect(submitted).toContain('disor-\nders')
    expect(submitted).toContain('thera-\npies')
    expect(submitted).toContain('ul-\ntrasound')
    await route.fulfill({json:{originalText:body.text,modelInputText:'disorders and therapies with ultrasound. high-intensity label-free\nunknown-\nword remains.',normalizationCount:3,translatedText:'Mock normalized translation',source:{documentId:doc.id,...body,sourceType:'translation'}}})
  })
  await page.getByRole('button',{name:'翻译所选文字'}).click()
  await expect(page.getByTestId('translation-result')).toHaveText('Mock normalized translation')
  await expect(page.getByTestId('translation-original')).toContainText('disor-')
  await expect(page.getByText(/已按.*PDF.*换行证据合并断词/)).toBeVisible()
  await page.locator('details summary').click()
  await expect(page.getByTestId('translation-model-input')).toContainText('disorders and therapies with ultrasound.')
  expect(submitted).toContain('high-intensity label-free')
})
