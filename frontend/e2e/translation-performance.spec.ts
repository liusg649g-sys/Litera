import {test,expect,type Page} from '@playwright/test'
import {openLibrary,upload} from './library-fixtures'
import {readerPdf} from './reader-fixtures'
async function setup(page:Page){
 const token=await openLibrary(page)
 const doc=await(await upload(page.request,token,readerPdf('Alpha sentence. Beta statement. Gamma clause. Delta conclusion.',1),'request-control.pdf')).json()
 await page.goto(`/reader/${doc.id}`)
 await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染')
 await page.getByRole('button',{name:'翻译面板',exact:true}).click()
 return doc
}
async function select(page:Page,word:string){
 await page.evaluate(word=>{const node=document.querySelector('.pdf-page[data-page="1"] .textLayer span')!.firstChild!;const start=node.textContent!.indexOf(word);const range=document.createRange();range.setStart(node,start);range.setEnd(node,start+word.length);window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)},word)
 await expect(page.getByTestId('translation-original')).toHaveText(word)
}
function translated(body:any,id:string){return {originalText:body.text,translatedText:'Mock '+body.text,source:{documentId:id,...body,sourceType:'translation'}}}
test('manual toolbar shares one request and shows current versus previous source (Mock)',async({page})=>{
 const doc=await setup(page);let calls=0;let release!:()=>void;const gate=new Promise<void>(resolve=>release=resolve)
 await page.route('**/api/v1/documents/*/translations',async route=>{calls++;const body=route.request().postDataJSON();await gate;await route.fulfill({json:translated(body,doc.id)})})
 await select(page,'Alpha');expect(calls).toBe(0)
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click()
 await expect.poll(()=>calls).toBe(1)
 await expect(page.getByRole('button',{name:'翻译所选文字',exact:true})).toBeDisabled()
 await expect(page.getByRole('button',{name:'翻译中…',exact:true})).toBeDisabled()
 await page.waitForTimeout(200);expect(calls).toBe(1)
 release();await expect(page.getByTestId('translation-result-state')).toHaveText('当前选区译文')
 await select(page,'Beta')
 await expect(page.getByTestId('translation-result-state')).toHaveText('上一条译文')
 await page.getByText('查看此译文对应的原文',{exact:true}).click()
 await expect(page.getByTestId('translation-result-original')).toHaveText('Alpha')
 await expect(page.getByLabel('文献翻译',{exact:true})).not.toContainText('此译文来源：')
 await page.getByRole('button',{name:'关闭文献翻译'}).click();await page.getByRole('button',{name:'翻译面板',exact:true}).click();expect(calls).toBe(1)
})
test('realtime debounces and sends only latest pending after slow request (Mock)',async({page})=>{
 const doc=await setup(page),calls:any[]=[];let release!:()=>void;const gate=new Promise<void>(resolve=>release=resolve)
 await page.route('**/api/v1/documents/*/translations',async route=>{const body=route.request().postDataJSON();calls.push(body);if(calls.length===1)await gate;await route.fulfill({json:translated(body,doc.id)})})
 await page.getByLabel('翻译模式',{exact:true}).selectOption('realtime')
 await select(page,'Alpha');await page.waitForTimeout(250);expect(calls).toHaveLength(0);await expect.poll(()=>calls.length).toBe(1)
 for(const word of ['Beta','Gamma','Delta']){await select(page,word);await page.waitForTimeout(550);expect(calls).toHaveLength(1)}
 await expect(page.getByText('等待上一请求结束，将翻译最新选区…',{exact:true})).toBeVisible()
 release();await expect.poll(()=>calls.length).toBe(2)
 await expect(page.getByTestId('translation-result')).toHaveText('Mock Delta')
 expect(calls.map(body=>body.text)).toEqual(['Alpha','Delta'])
 await expect(page.getByTestId('translation-result-state')).toHaveText('当前选区译文')
})
test('gateway429 pauses realtime instead of automatically retrying pending selections (Mock)',async({page})=>{
 const doc=await setup(page);let calls=0
 await page.route('**/api/v1/documents/*/translations',async route=>{calls++;const body=route.request().postDataJSON();await route.fulfill(calls===1?{status:429,json:{error:{code:'MODEL_QUOTA',message:'Mock gateway limit'}}}:{json:translated(body,doc.id)})})
 await page.getByLabel('翻译模式',{exact:true}).selectOption('realtime');await select(page,'Alpha')
 await expect(page.getByRole('alert')).toContainText('Mock gateway limit')
 await expect(page.getByText('实时翻译已暂停，请稍后手动重试。',{exact:true})).toBeVisible()
 await select(page,'Delta');await page.waitForTimeout(850);expect(calls).toBe(1)
 await page.getByRole('button',{name:'翻译',exact:true}).click()
 await expect(page.getByTestId('translation-result')).toHaveText('Mock Delta');expect(calls).toBe(2)
 await expect(page.getByText('实时翻译已暂停，请稍后手动重试。',{exact:true})).toHaveCount(0)
})
