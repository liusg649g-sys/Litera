import {test,expect,type Page} from '@playwright/test'
import {openLibrary,upload} from './library-fixtures'
import {readerPdf} from './reader-fixtures'
async function setup(page:Page){const token=await openLibrary(page);const doc=await(await upload(page.request,token,readerPdf('Translation selection sample',3),'translation.pdf')).json();await page.goto(`/reader/${doc.id}`);await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染');return doc}
async function select(page:Page){await page.evaluate(()=>{const node=document.querySelector('.pdf-page[data-page="1"] .textLayer span')!.firstChild!;const range=document.createRange();range.selectNodeContents(node);window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)});await page.waitForTimeout(150)}
async function mock(page:Page,calls:any[],fail=false){await page.route('**/api/v1/documents/*/translations',async route=>{const body=route.request().postDataJSON();calls.push(body);await route.fulfill({status:fail?503:200,json:fail?{error:{code:'MODEL_UNAVAILABLE',message:'Mock model unavailable'}}:{originalText:body.text,translatedText:'Mock translated paragraph',source:{documentId:route.request().url().split('/').at(-2),...body,sourceType:'translation'}}})})}
test('translation manual directions and collapse preserve PDF source (Mock model)',async({page})=>{const doc=await setup(page),calls:any[]=[];await mock(page,calls);await select(page);await page.getByRole('button',{name:'翻译面板',exact:true}).click();await expect(page.getByTestId('translation-original')).toContainText('Translation');expect(calls).toHaveLength(0);await page.getByRole('button',{name:'翻译',exact:true}).click();await expect(page.getByTestId('translation-result')).toHaveText('Mock translated paragraph');expect(calls[0]).toMatchObject({pageNumber:1,sourceLanguage:'en',targetLanguage:'zh'});await expect(page.getByTestId('translation-source')).toHaveText(`${doc.title} · PDF 第 1 页`);await expect(page.getByTestId('translation-result-source')).toContainText(`${doc.title} · PDF 第 1 页`);await expect(page.getByLabel('文献翻译',{exact:true})).not.toContainText(doc.id);await page.getByRole('button',{name:'关闭文献翻译'}).click();await page.getByRole('button',{name:'翻译面板',exact:true}).click();await expect(page.getByTestId('translation-result')).toHaveText('Mock translated paragraph');await page.getByLabel('语言方向',{exact:true}).selectOption('zh-en');await page.getByRole('button',{name:'翻译',exact:true}).click();await expect.poll(()=>calls.length).toBe(2);expect(calls[1]).toMatchObject({sourceLanguage:'zh',targetLanguage:'en'});await page.screenshot({path:'test-results/translation-desktop.png'})})
test('translation realtime pauses collapsed and explicit translation opens (Mock model)',async({page})=>{await setup(page);const calls:any[]=[];await mock(page,calls);await page.getByRole('button',{name:'翻译面板',exact:true}).click();await page.getByLabel('翻译模式',{exact:true}).selectOption('realtime');await select(page);await expect.poll(()=>calls.length).toBe(1);await expect(page.getByTestId('translation-result')).toBeVisible();await page.getByRole('button',{name:'关闭文献翻译'}).click();await select(page);await page.waitForTimeout(650);expect(calls).toHaveLength(1);await page.getByRole('button',{name:'翻译所选文字'}).click();await expect(page.getByTestId('translation-result')).toBeVisible();await expect.poll(()=>calls.length).toBe(2)})
test('translation failure retains source, retries, narrow PDF remains readable (Mock model)',async({page})=>{await setup(page);const calls:any[]=[];await mock(page,calls,true);await select(page);await page.getByRole('button',{name:'翻译所选文字'}).click();await expect(page.getByRole('alert')).toContainText('Mock model unavailable');await expect(page.getByTestId('translation-original')).toContainText('Translation');await page.unroute('**/api/v1/documents/*/translations');await mock(page,calls);await page.getByRole('button',{name:'重试翻译'}).click();await expect(page.getByTestId('translation-result')).toHaveText('Mock translated paragraph');await page.setViewportSize({width:390,height:844});await expect(page.getByRole('dialog',{name:'文献翻译',exact:true})).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:'test-results/translation-narrow.png'});await page.getByRole('button',{name:'关闭文献翻译'}).click();await expect(page.getByLabel('PDF 阅读区域',{exact:true})).toBeVisible()})
test('translation real unconfigured backend returns explicit error',async({page})=>{await setup(page);await select(page);await page.getByRole('button',{name:'翻译所选文字'}).click();await expect(page.getByRole('alert')).toContainText('模型未配置');await expect(page.getByTestId('translation-original')).toContainText('Translation');await expect(page.getByTestId('translation-result')).toHaveCount(0)})

test('translation copy success and clipboard failure are explicit (Mock clipboard/model)',async({page})=>{await setup(page);await mock(page,[]);await select(page);await page.getByRole('button',{name:'翻译所选文字'}).click();await expect(page.getByTestId('translation-result')).toHaveText('Mock translated paragraph');await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async(text:string)=>{(window as any).__copiedTranslation=text}}}));await page.getByRole('button',{name:'复制译文'}).click();await expect(page.getByText('已复制译文',{exact:true})).toBeVisible();expect(await page.evaluate(()=>(window as any).__copiedTranslation)).toBe('Mock translated paragraph');await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw new Error('denied')}}}));await page.getByRole('button',{name:'复制译文'}).click();await expect(page.getByText('复制失败，请手动选择译文复制',{exact:true})).toBeVisible()})


test('manual P2-A word sentence paragraph retain exact text and physical page (Mock model)',async({page})=>{
  const token=await openLibrary(page)
  const doc=await(await upload(page.request,token,readerPdf('First sentence. Second sentence.',3),'manual-page.pdf')).json()
  await page.goto(`/reader/${doc.id}`)
  await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染')
  await page.getByLabel('当前页码',{exact:true}).fill('2');await page.getByLabel('当前页码',{exact:true}).press('Enter')
  await expect(page.locator('.pdf-page[data-page="2"]')).toHaveAttribute('data-status','已渲染')
  const calls:any[]=[]
  let releaseResponse:(()=>void)|undefined
  await page.route('**/api/v1/documents/*/translations',async route=>{
    const body=route.request().postDataJSON();calls.push(body)
    // Keep the response pending until the test has observed the loading state.
    await new Promise<void>(resolve=>{releaseResponse=resolve})
    await route.fulfill({status:200,json:{originalText:body.text,translatedText:'Mock translation '+body.text,source:{documentId:doc.id,...body,sourceType:'translation'}}})
  })
  await page.getByRole('button',{name:'翻译面板',exact:true}).click()
  for(const kind of ['word','sentence','paragraph']){
    const text=await page.evaluate(kind=>{
      const node=document.querySelector('.pdf-page[data-page="2"] .textLayer span')!.firstChild!
      const full=node.textContent!,end=kind==='word'?5:kind==='sentence'?full.indexOf('.')+1:full.length
      const range=document.createRange();range.setStart(node,0);range.setEnd(node,end)
      window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)
      return full.slice(0,end)
    },kind)
    await expect(page.getByTestId('translation-original')).toHaveText(text)
    const before=calls.length;await page.waitForTimeout(550);expect(calls).toHaveLength(before)
    await page.getByRole('button',{name:'翻译',exact:true}).click()
    await expect.poll(()=>calls.length).toBe(before+1)
    try{await expect(page.getByText('正在翻译…',{exact:true})).toBeVisible()}
    finally{releaseResponse?.();releaseResponse=undefined}
    await expect(page.getByTestId('translation-result')).toHaveText('Mock translation '+text)
    expect(calls.at(-1)).toMatchObject({text,pageNumber:2,sourceLanguage:'en',targetLanguage:'zh'})
  }
})


function opaqueTextPdf(){
 const content='BT /F1 18 Tf 40 700 Td <010203> Tj ET'
 const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',`<< /Length ${content.length} >>\nstream\n${content}\nendstream`,'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /FirstChar 1 /LastChar 3 /Widths [600 600 600] /Encoding << /Type /Encoding /Differences [1 /G01 /G02 /G03] >> >>']
 let text='%PDF-1.7\n';const offsets=[0]
 for(const [i,object] of objects.entries()){offsets.push(Buffer.byteLength(text));text+=`${i+1} 0 obj\n${object}\nendobj\n`}
 const xref=Buffer.byteLength(text)
 text+=`xref\n0 6\n0000000000 65535 f \n`+offsets.slice(1).map(n=>`${String(n).padStart(10,'0')} 00000 n \n`).join('')
 return Buffer.from(text+`trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`)
}
async function verifyBadMapping(page:Page,bytes:Buffer,number:number){
 const token=await openLibrary(page),doc=await(await upload(page.request,token,bytes,'mapping-fixture.pdf')).json()
 await page.goto(`/reader/${doc.id}`);await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染')
 if(number!==1){await page.getByLabel('当前页码',{exact:true}).fill(String(number));await page.getByLabel('当前页码',{exact:true}).press('Enter')}
 await expect(page.locator(`.pdf-page[data-page="${number}"]`)).toHaveAttribute('data-status','已渲染')
 let calls=0;await page.route('**/api/v1/documents/*/translations',async route=>{calls++;await route.abort()})
 await page.getByRole('button',{name:'翻译面板',exact:true}).click()
 await page.evaluate(number=>{const spans=[...document.querySelectorAll(`.pdf-page[data-page="${number}"] .textLayer span`)];const span=spans.find(el=>el.textContent!.length>12)||spans[0]!;const range=document.createRange();range.selectNodeContents(span);window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)},number)
 await expect(page.getByTestId('translation-original')).toContainText('无法可靠提取原文')
 await expect(page.getByRole('button',{name:'翻译',exact:true})).toBeDisabled()
 await page.getByRole('button',{name:'翻译所选文字'}).click();await page.waitForTimeout(600)
 expect(calls).toBe(0);await expect(page.getByRole('alert')).toHaveCount(1);await expect(page.getByRole('alert')).toContainText('已阻止翻译')
}
test('opaque font PDF is visible but its unmapped text is never translated',async({page})=>{await verifyBadMapping(page,opaqueTextPdf(),1)})
test('opt-in reported PDF page five blocks unreliable source (local private fixture)',async({page})=>{
 test.skip(!process.env.LITERA_MAPPING_PDF,'Only run when the user supplies a local diagnostic PDF; never commit its content')
 const {readFile}=await import('node:fs/promises');await verifyBadMapping(page,await readFile(process.env.LITERA_MAPPING_PDF!),5)
})
