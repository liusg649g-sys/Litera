import {test,expect,type Page} from '@playwright/test'
import {randomUUID} from 'node:crypto'
import {readFileSync} from 'node:fs'
import {readerPdf} from './reader-fixtures'

// All accounts/documents in this file are created in disposable SQLite on 8005.
// The model adapter is a labelled isolated Mock. No private PDFs or model service.
const origin='http://127.0.0.1:5182'
type Doc={id:string;title:string}
const dialog=(page:Page)=>page.getByRole('dialog',{name:'保存到文献笔记',exact:true})
const headers=(token:string)=>({Origin:origin,'X-CSRF-Token':token})
async function setup(page:Page,count=1){
 const email=`captures-${Date.now()}-${randomUUID()}@example.com`
 expect((await page.request.post('/api/v1/auth/register',{headers:{Origin:origin},data:{email,password:'Litera-test-123',displayName:'隔离摘录验收'}})).status()).toBe(201)
 const login=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password:'Litera-test-123'}})
 expect(login.status()).toBe(200)
 const token=(await login.json()).csrfToken as string,docs:Doc[]=[]
 for(let index=0;index<count;index++){
  const bytes=readerPdf(`Capture public source ${index===0?'A':'B'}`,3)
  const response=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name:`Capture fixture ${index}.pdf`,mimeType:'application/pdf',buffer:bytes}}})
  expect(response.status()).toBe(201);docs.push(await response.json())
 }
 await open(page,docs[0]!)
 return {email,token,docs}
}
async function open(page:Page,doc:Doc){
 await page.goto(`/reader/${doc.id}`)
 await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
}
async function select(page:Page,pageNumber=1,word=false){
 if(pageNumber!==1){await page.getByLabel('当前页码',{exact:true}).fill(String(pageNumber));await page.getByLabel('当前页码',{exact:true}).press('Enter')}
 await expect(page.locator(`.pdf-page[data-page="${pageNumber}"]`)).toHaveAttribute('data-status','已渲染',{timeout:15000})
 const raw=await page.evaluate(({pageNumber,word})=>{
  const spans=[...document.querySelectorAll<HTMLElement>(`.pdf-page[data-page="${pageNumber}"] .textLayer span`)]
  const span=(word?spans.find(item=>/\s/.test(item.textContent||'')):undefined) ?? spans.find(item=>item.textContent?.length)
  const node=span?.firstChild
  if(!node)throw new Error('No selectable PDF.js text span')
  const full=node.textContent||''
  const split=full.search(/\s/)
  const range=document.createRange();range.setStart(node,0);range.setEnd(node,word&&split>0?split:full.length)
  const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range)
  return range.toString()
 },{pageNumber,word})
 await page.waitForTimeout(150)
 return raw.trim()
}
async function selectFirstParagraph(page:Page){
 const raw=await page.evaluate(()=>{
  const spans=[...document.querySelectorAll<HTMLElement>('.pdf-page[data-page="1"] .textLayer span')]
  const start=spans.findIndex(span=>(span.textContent?.trim().length||0)>50)
  if(start<0)throw new Error('No paragraph-like PDF.js text span')
  let end=start,nonempty=0
  while(end+1<spans.length && nonempty<5){end++;if(spans[end]!.textContent?.trim())nonempty++}
  const first=spans[start]!.firstChild!,last=spans[end]!.firstChild!
  const range=document.createRange();range.setStart(first,0);range.setEnd(last,last.textContent!.length)
  const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range)
  return range.toString()
 })
 await page.waitForTimeout(150)
 return raw.trim()
}
async function chooseNew(page:Page,title:string){
 const modal=dialog(page);await expect(modal).toBeVisible()
 const target=modal.getByRole('radio',{name:'新建笔记',exact:true})
 if(await target.count())await target.check()
 await modal.getByLabel('新笔记标题',{exact:true}).fill(title)
}
async function chooseExisting(page:Page,title:string){
 const modal=dialog(page)
 await modal.getByRole('radio',{name:'其他已有笔记',exact:true}).check()
 await modal.getByLabel('搜索已有笔记标题',{exact:true}).fill(title)
 await modal.getByRole('button',{name:'搜索笔记',exact:true}).click()
 await modal.getByRole('button',{name:`选择笔记：${title}`,exact:true}).click()
}
async function save(page:Page){
 const pending=page.waitForResponse(response=>response.request().method()==='POST' && response.url().endsWith('/api/v1/notes/captures'))
 await dialog(page).getByRole('button',{name:'保存摘录',exact:true}).click()
 const response=await pending
 expect(response.status(),await response.text()).toBe(201)
 const result=await response.json()
 await expect(dialog(page)).not.toBeVisible()
 return result
}
async function readNote(page:Page,id:string){const response=await page.request.get(`/api/v1/notes/${id}`);expect(response.status()).toBe(200);return response.json()}
async function createNote(page:Page,token:string,doc:Doc,title:string,content='Private editable thoughts'){
 const id=randomUUID(),response=await page.request.post('/api/v1/notes',{headers:headers(token),data:{id,title,content,documentId:doc.id}})
 expect(response.status()).toBe(201);return response.json()
}
async function showNote(page:Page,title:string){
 const panel=page.getByLabel('文献笔记',{exact:true})
 if(!await panel.isVisible())await page.getByRole('button',{name:'笔记面板',exact:true}).click()
 await page.getByRole('button',{name:`打开笔记：${title}`,exact:true}).click()
 await expect(page.getByLabel('笔记标题',{exact:true})).toHaveValue(title)
}
async function expectSource(page:Page,blockId:string,doc:Doc,number:number,raw:string){
 const region=page.getByRole('region',{name:'笔记来源摘录',exact:true})
 await expect(region).toBeVisible();await expect(region).toContainText(doc.title)
 await expect(region).toContainText(`PDF 第 ${number} 页`)
 const card=region.locator(`[data-source-block-id="${blockId}"]`)
 await expect(card).toContainText(raw)
}
async function expectExactHighlight(page:Page,pageNumber:number,minimum=1){
 const pageNode=page.locator(`.pdf-page[data-page="${pageNumber}"]`),marks=pageNode.getByTestId('source-highlight')
 await expect.poll(()=>marks.count(),{timeout:15000}).toBeGreaterThanOrEqual(minimum)
 expect(await pageNode.evaluate(host=>{
  const pageBounds=host.getBoundingClientRect()
  return [...host.querySelectorAll<HTMLElement>('[data-testid="source-highlight"]')].every(node=>{const bounds=node.getBoundingClientRect();return bounds.width>0&&bounds.height>0&&bounds.left>=pageBounds.left-1&&bounds.right<=pageBounds.right+1&&bounds.top>=pageBounds.top-1&&bounds.bottom<=pageBounds.bottom+1})
 })).toBe(true)
}

test('PDF selection creates structured source in a new note and persists after refresh and relogin (real temporary SQLite)',async({page})=>{
 const {email,token,docs}=await setup(page),a=docs[0]!,raw=await select(page,2)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click()
 await chooseNew(page,'Source with physical page two')
 const result=await save(page),note=await readNote(page,result.note.id)
 expect(note.content).toBe('');expect(note.sources).toHaveLength(1)
 const block=note.sources[0]
 expect(block).toMatchObject({id:result.blockId,kind:'pdf_excerpt',originalText:raw,source:{documentId:a.id,title:a.title,pageNumber:2,precision:'page'}})
 expect(block.source.positions[0].rects.length).toBeGreaterThan(0)
 expect(block.source.positions[0].textQuote).toBe(raw)
 expect(block.source.fileSha256).toMatch(/^[a-f0-9]{64}$/)
 expect(note.documents.map((document:Doc)=>document.id)).toEqual([a.id])
 await expectSource(page,block.id,a,2,raw)
 const keyword=raw.split(/\s+/).find((value:string)=>value.length>=4)!.slice(0,8)
 const sourceSearch=page.waitForResponse(response=>response.url().includes('/api/v1/notes/search?') && new URL(response.url()).searchParams.get('q')===keyword)
 await page.getByLabel('搜索个人笔记关键词',{exact:true}).fill(keyword);expect((await sourceSearch).status()).toBe(200)
 const sourceResult=page.getByRole('region',{name:'笔记搜索结果',exact:true}).locator(`article[data-note-id="${note.id}"]`)
 await expect(sourceResult.locator('[data-match-field="source_original"]')).toBeVisible()
 await page.getByRole('button',{name:'清空笔记搜索',exact:true}).click()
 await page.getByRole('button',{name:'关闭文献笔记',exact:true}).click();await page.getByRole('button',{name:'笔记面板',exact:true}).click()
 await expectSource(page,block.id,a,2,raw)
 await page.reload();await showNote(page,note.title);await expectSource(page,block.id,a,2,raw)
 expect((await page.request.post('/api/v1/auth/logout',{headers:headers(token)})).status()).toBe(204)
 await page.goto('/login');await page.getByLabel('邮箱',{exact:true}).fill(email);await page.getByLabel('密码',{exact:true}).fill('Litera-test-123');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL('/library')
 await open(page,a);await showNote(page,note.title);await expectSource(page,block.id,a,2,raw)
 expect((await readNote(page,note.id)).sources).toEqual(note.sources)
})

test('existing note requires an explicit new association and preserves source A while editing from B or unlinking A (real SQLite)',async({page})=>{
 const {token,docs}=await setup(page,2),a=docs[0]!,b=docs[1]!
 const note=await createNote(page,token,b,'Shared immutable source')
 const raw=await select(page)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseExisting(page,note.title)
 await expect(dialog(page).getByRole('button',{name:'保存摘录',exact:true})).toBeDisabled()
 await dialog(page).getByRole('radio',{name:'同时关联来源文献',exact:true}).check()
 const result=await save(page),inserted=await readNote(page,note.id)
 expect(new Set(inserted.documents.map((document:Doc)=>document.id))).toEqual(new Set([a.id,b.id]))
 expect(inserted.content).toBe('Private editable thoughts')
 await page.getByRole('region',{name:'关联文献',exact:true}).getByRole('button',{name:`打开关联文献：${b.title}`,exact:true}).click()
 await expect(page).toHaveURL(`/reader/${b.id}`)
 await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 await expectSource(page,result.blockId,a,1,raw)
 await page.getByLabel('笔记正文',{exact:true}).fill('My own thoughts changed from B; original quotation remains immutable.')
 await expect.poll(async()=>(await readNote(page,note.id)).content).toBe('My own thoughts changed from B; original quotation remains immutable.')
 expect((await readNote(page,note.id)).sources).toEqual(inserted.sources)
 expect((await page.request.delete(`/api/v1/notes/${note.id}/documents/${a.id}`,{headers:headers(token)})).status()).toBe(200)
 await page.reload();await showNote(page,note.title)
 await expectSource(page,result.blockId,a,1,raw)
 await expect(page.getByRole('region',{name:'笔记来源摘录',exact:true})).toContainText('来源文献当前未关联')
 const retained=await readNote(page,note.id)
 expect(retained.documents.map((document:Doc)=>document.id)).toEqual([b.id]);expect(retained.sources).toEqual(inserted.sources)
 await page.setViewportSize({width:390,height:844})
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
 await page.getByRole('region',{name:'笔记来源摘录',exact:true}).scrollIntoViewIfNeeded()
 await page.screenshot({path:'test-results/note-captures/source-blocks-narrow.png'})
})

test('saving only a source never silently changes the association set (real SQLite)',async({page})=>{
 const {token,docs}=await setup(page,2),a=docs[0]!,b=docs[1]!,note=await createNote(page,token,b,'Keep source without relation')
 const raw=await select(page)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseExisting(page,note.title)
 await dialog(page).getByRole('radio',{name:'仅保存来源，不新增关联',exact:true}).check()
 const result=await save(page),saved=await readNote(page,note.id)
 expect(saved.documents.map((document:Doc)=>document.id)).toEqual([b.id])
 expect(saved.sources[0]).toMatchObject({id:result.blockId,originalText:raw,source:{documentId:a.id}})
 expect((await(await page.request.get(`/api/v1/notes?documentId=${a.id}`)).json()).items.some((item:{id:string})=>item.id===note.id)).toBe(false)
 await open(page,b);await showNote(page,note.title);await expectSource(page,result.blockId,a,1,raw)
})

test('current translation saves original, direction, provenance and server-verified source (isolated Mock model, real HTTP)',async({page})=>{
 const {docs}=await setup(page),a=docs[0]!,raw=await select(page)
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click()
 await expect(page.getByTestId('translation-result')).toContainText('隔离 Mock')
 await page.getByRole('button',{name:'保存到笔记',exact:true}).click();await chooseNew(page,'Current translated excerpt')
 const result=await save(page),note=await readNote(page,result.note.id),block=note.sources[0]
 expect(block).toMatchObject({kind:'translation_excerpt',originalText:raw,sourceLanguage:'en',targetLanguage:'zh',translationProvenance:'isolated_mock',historical:false,source:{documentId:a.id,pageNumber:1}})
 expect(block.translatedText).toContain('隔离 Mock')
 expect(block).not.toHaveProperty('translationProof')
 await expectSource(page,block.id,a,1,raw)
 await expect(page.getByRole('region',{name:'笔记来源摘录',exact:true})).toContainText('非真实模型')
 const translatedSearch=page.waitForResponse(response=>response.url().includes('/api/v1/notes/search?') && new URL(response.url()).searchParams.get('q')==='隔离 Mock')
 await page.getByLabel('搜索个人笔记关键词',{exact:true}).fill('隔离 Mock');expect((await translatedSearch).status()).toBe(200)
 await expect(page.getByRole('region',{name:'笔记搜索结果',exact:true}).locator('[data-match-field="source_translation"]')).toBeVisible()
 await page.getByRole('button',{name:'清空笔记搜索',exact:true}).click()
 await page.setViewportSize({width:1920,height:1100})
 await page.getByRole('region',{name:'笔记来源摘录',exact:true}).scrollIntoViewIfNeeded()
 await page.screenshot({path:'test-results/note-captures/translation-source-desktop.png'})
})

test('a previous translation needs explicit history confirmation and keeps its own full text (isolated Mock)',async({page})=>{
 const {docs}=await setup(page),a=docs[0]!,raw=await select(page)
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click();await expect(page.getByTestId('translation-result')).toContainText('隔离 Mock')
 const current=await select(page,1,true);expect(current).not.toBe(raw)
 await expect(page.getByTestId('translation-result-state')).toHaveText('上一条译文')
 await page.getByRole('button',{name:'保存到笔记',exact:true}).click();await chooseNew(page,'Explicit previous translation')
 await expect(dialog(page)).toContainText('上一条译文')
 await expect(dialog(page).getByRole('button',{name:'保存摘录',exact:true})).toBeDisabled()
 await dialog(page).getByRole('checkbox',{name:'确认保存上一条译文及其原来源',exact:true}).check()
 const result=await save(page),note=await readNote(page,result.note.id)
 expect(note.sources[0]).toMatchObject({originalText:raw,historical:true,source:{documentId:a.id,pageNumber:1}})
 expect(note.sources[0].originalText).not.toBe(current)
})

test('local opt-in normal PDF saves PDF.js paragraph and historical Mock with their own source',async({page})=>{
 const localPdf=process.env.LITERA_P3B_REPRO_PDF
 test.skip(!localPdf,'Set LITERA_P3B_REPRO_PDF to the local non-committed reproduction PDF')
 const {token}=await setup(page)
 const upload=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name:'local-p3b-reproduction.pdf',mimeType:'application/pdf',buffer:readFileSync(localPdf!)}}})
 expect(upload.status(),await upload.text()).toBe(201)
 const doc=await upload.json() as Doc;await open(page,doc)
 const raw=await selectFirstParagraph(page)
 const capturedOriginals:string[]=[];let translatedOriginal=''
 page.on('request',request=>{
  const body=request.postDataJSON?.()
  if(request.method()==='POST' && request.url().endsWith('/api/v1/notes/captures'))capturedOriginals.push(body.source.originalText)
  if(request.method()==='POST' && request.url().endsWith('/translations'))translatedOriginal=body.text
 })
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Local PDF original excerpt')
 const original=await save(page),originalNote=await readNote(page,original.note.id)
 expect(capturedOriginals[0]).toBeTruthy()
 expect(originalNote.sources[0]).toMatchObject({kind:'pdf_excerpt',originalText:capturedOriginals[0],source:{documentId:doc.id,pageNumber:1}})
 await selectFirstParagraph(page)
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click()
 await expect(page.getByTestId('translation-result')).toContainText('隔离 Mock')
 const latest=await select(page,1,true);expect(latest).not.toBe(raw)
 await expect(page.getByTestId('translation-result-state')).toHaveText('上一条译文')
 await page.getByRole('button',{name:'保存到笔记',exact:true}).click();await chooseNew(page,'Local PDF historical Mock excerpt')
 await dialog(page).getByRole('checkbox',{name:'确认保存上一条译文及其原来源',exact:true}).check()
 const history=await save(page),historyNote=await readNote(page,history.note.id)
 expect(translatedOriginal).toBeTruthy()
 expect(historyNote.sources[0]).toMatchObject({kind:'translation_excerpt',originalText:translatedOriginal,historical:true,translationProvenance:'isolated_mock',source:{documentId:doc.id,pageNumber:1}})
 expect(historyNote.sources[0].originalText).not.toBe(latest)
})

test('late translation response cannot replace a changed selection or become a captured current translation (Mock delayed transport)',async({page})=>{
 await setup(page);const original=await select(page)
 let intercepted=0
 await page.route('**/api/v1/documents/*/translations',async route=>{const response=await route.fetch();intercepted++;await new Promise(resolve=>setTimeout(resolve,450));await route.fulfill({response})})
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click();await expect.poll(()=>intercepted).toBe(1)
 const latest=await select(page,1,true);expect(latest).not.toBe(original)
 await page.waitForTimeout(550)
 await expect(page.getByTestId('translation-original')).toHaveText(latest)
 await expect(page.getByTestId('translation-result')).toHaveCount(0)
 await expect(page.getByRole('button',{name:'保存到笔记',exact:true})).toHaveCount(0)
 await page.unroute('**/api/v1/documents/*/translations')
 await page.getByRole('button',{name:'翻译所选文字',exact:true}).click();await expect(page.getByTestId('translation-result')).toContainText(latest)
})

test('lost response after a real commit is retried with the same operation and never duplicates a source (Mock network fault)',async({page})=>{
 await setup(page);await select(page)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Idempotent captured note')
 let operation='',noteId='',calls=0
 await page.route('**/api/v1/notes/captures',async route=>{
  calls++;const body=route.request().postDataJSON()
  if(!operation){operation=body.operationId;noteId=body.noteId}else expect(body.operationId).toBe(operation)
  const response=await route.fetch()
  if(calls===1){expect(response.status()).toBe(201);await route.abort('failed')}else await route.fulfill({response})
 })
 await dialog(page).getByRole('button',{name:'保存摘录',exact:true}).click()
 await expect(dialog(page).getByRole('alert')).toBeVisible()
 await expect.poll(async()=>noteId?(await readNote(page,noteId)).sources.length:0).toBe(1)
 await expect(dialog(page)).toContainText('Capture public source')
 const replay=page.waitForResponse(response=>response.request().method()==='POST' && response.url().endsWith('/api/v1/notes/captures'))
 await dialog(page).getByRole('button',{name:'重试保存',exact:true}).click();const response=await replay
 expect(response.status()).toBe(200);expect((await response.json()).replayed).toBe(true)
 await expect(dialog(page)).not.toBeVisible()
 expect(calls).toBe(2);expect((await readNote(page,noteId)).sources).toHaveLength(1)
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

test('unmapped PDF text is never captured as a reliable original (real abnormal synthetic PDF)',async({page})=>{
 const {token}=await setup(page)
 const response=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name:'opaque-fixture.pdf',mimeType:'application/pdf',buffer:opaqueTextPdf()}}})
 expect(response.status()).toBe(201);await open(page,await response.json())
 let captures=0;page.on('request',request=>{if(request.method()==='POST' && request.url().endsWith('/api/v1/notes/captures'))captures++})
 await select(page)
 const button=page.getByRole('button',{name:'添加到笔记',exact:true})
 if(await button.isEnabled())await button.click()
 else await expect(button).toBeDisabled()
 await expect(dialog(page)).not.toBeVisible();expect(captures).toBe(0)
 await page.getByRole('button',{name:'翻译面板',exact:true}).click()
 await expect(page.getByTestId('translation-original')).toContainText('无法可靠提取原文')
})

test('current note is recommended without forcing the target and ordinary editor selection is not a PDF excerpt (real PDF.js)',async({page})=>{
 const {token,docs}=await setup(page),a=docs[0]!,note=await createNote(page,token,a,'Recommended active note','Author thoughts are not PDF text')
 await showNote(page,note.title)
 await page.getByLabel('笔记正文',{exact:true}).evaluate(node=>{const input=node as HTMLTextAreaElement;input.focus();input.select()})
 let captures=0;page.on('request',request=>{if(request.method()==='POST' && request.url().endsWith('/api/v1/notes/captures'))captures++})
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click()
 await expect(dialog(page)).not.toBeVisible();expect(captures).toBe(0)
 const raw=await select(page)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click()
 await expect(dialog(page).getByRole('radio',{name:'当前笔记',exact:true})).toBeChecked()
 const result=await save(page)
 expect(result.note.id).toBe(note.id)
 expect((await readNote(page,note.id)).content).toBe('Author thoughts are not PDF text')
 await expectSource(page,result.blockId,a,1,raw)
 expect(captures).toBe(1)
})

test('structured source navigation opens the exact PDF page, preserves draft and works from search (real SQLite/PDF.js)',async({page})=>{
 test.setTimeout(120000)
 const {token,docs}=await setup(page,2),a=docs[0]!,b=docs[1]!,raw=await select(page,2)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Exact source navigation')
 const result=await save(page),note=await readNote(page,result.note.id)
 expect(note.sources[0]).toMatchObject({source:{documentId:a.id,pageNumber:2}})
 expect((await page.request.put(`/api/v1/notes/${note.id}/documents/${b.id}`,{headers:headers(token)})).status()).toBe(200)
 await open(page,b);await showNote(page,note.title)
 const before=await readNote(page,note.id)
 await page.getByLabel('笔记正文',{exact:true}).fill('Draft saved before opening exact source page')
 await page.getByRole('button',{name:`查看原文：${a.title}，PDF 第 2 页`,exact:true}).click()
 await expect(page).toHaveURL(`/reader/${a.id}`)
 await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2')
 await expect(page.locator('.pdf-page[data-page="2"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 await expect(page.getByLabel('笔记正文',{exact:true})).toHaveValue('Draft saved before opening exact source page')
 await expect(page.getByTestId('note-navigation-success')).toContainText('精确定位')
 await expectExactHighlight(page,2)
 const saved=await readNote(page,note.id)
 expect(saved.content).toBe('Draft saved before opening exact source page')
 expect(saved.documents.map((document:Doc)=>document.id).sort()).toEqual([a.id,b.id].sort())
 expect(saved.sources).toEqual(before.sources)

 // Same-document navigation reuses the current tab and the same source snapshot.
 await page.getByLabel('当前页码',{exact:true}).fill('1');await page.getByLabel('当前页码',{exact:true}).press('Enter')
 await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('1')
 const sameDocumentCheck=page.waitForResponse(response=>response.request().method()==='GET' && new URL(response.url()).pathname===`/api/v1/documents/${a.id}`)
 await page.getByRole('button',{name:`查看原文：${a.title}，PDF 第 2 页`,exact:true}).click();await sameDocumentCheck
 await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2')
 await expectExactHighlight(page,2)
 await expect(page.getByText('正在核对并打开笔记来源…',{exact:true})).toHaveCount(0)

 // A source-page jump can surface the reader's existing cross-session progress guard.
 // Resolve it through the public UI before exercising a separate workspace-tab action.
 const progressConflict=page.getByRole('alert').filter({hasText:'未同步的本地阅读进度'})
 if(await progressConflict.isVisible()) await progressConflict.getByRole('button',{name:'载入服务端进度',exact:true}).click()

 // P3-C1 search opens the same note; its source action remains available.
 await page.locator(`.reader-tab[data-tab-id="${b.id}"] .document-title`).click();await expect(page).toHaveURL(`/reader/${b.id}`,{timeout:10000})
 await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 const keyword=raw.split(/\s+/).find((value:string)=>value.length>=4)!.slice(0,8)
 const pending=page.waitForResponse(response=>response.url().includes('/api/v1/notes/search?') && new URL(response.url()).searchParams.get('q')===keyword)
 await page.getByLabel('搜索个人笔记关键词',{exact:true}).fill(keyword);expect((await pending).status()).toBe(200)
 await page.getByRole('region',{name:'笔记搜索结果',exact:true}).getByRole('button',{name:`打开搜索结果：${note.title}`,exact:true}).click()
 await page.getByRole('button',{name:`查看原文：${a.title}，PDF 第 2 页`,exact:true}).click()
 await expect(page).toHaveURL(`/reader/${a.id}`);await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2');await expectExactHighlight(page,2)
 expect((await readNote(page,note.id)).documents).toEqual(saved.documents)
})

test('source navigation rejects a changed PDF digest before switching documents (real HTTP with controlled response fault)',async({page})=>{
 test.setTimeout(90000)
 const {docs}=await setup(page,2),a=docs[0]!,b=docs[1]!,raw=await select(page,2)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Version protected source')
 const result=await save(page),note=await readNote(page,result.note.id)
 await open(page,b)
 await page.getByRole('button',{name:'笔记面板',exact:true}).click()
 // The note is not associated with B; open it through P3-C1 search.
 const keyword=raw.split(/\s+/).find((value:string)=>value.length>=4)!.slice(0,8)
 const pending=page.waitForResponse(response=>response.url().includes('/api/v1/notes/search?') && new URL(response.url()).searchParams.get('q')===keyword)
 await page.getByLabel('搜索个人笔记关键词',{exact:true}).fill(keyword);await pending
 await page.getByRole('region',{name:'笔记搜索结果',exact:true}).getByRole('button',{name:`打开搜索结果：${note.title}`,exact:true}).click()
 await page.route(`**/api/v1/documents/${a.id}`,async route=>{
  const response=await route.fetch(),body=await response.json()
  await route.fulfill({response,json:{...body,attachment:{...body.attachment,sha256:'f'.repeat(64)}}})
 })
 await page.getByRole('button',{name:`查看原文：${a.title}，PDF 第 2 页`,exact:true}).click()
 await expect(page.getByTestId('note-navigation-error')).toContainText('无法可靠定位来源')
 await expect(page.getByTestId('note-navigation-error')).toContainText('版本不一致')
 await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 await expect(page).toHaveURL(`/reader/${b.id}`)
 expect((await readNote(page,note.id)).sources[0].source.documentId).toBe(a.id)
})

test('multi-line PDF.js ranges render separate temporary highlights (real temporary SQLite/PDF.js)',async({page})=>{
 test.setTimeout(90000)
 const {token}=await setup(page)
 const bytes=readerPdf('Multi line highlight',1,false,{lines:['First exact source line','Second exact source line']})
 const uploaded=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name:'multi-line-highlight.pdf',mimeType:'application/pdf',buffer:bytes}}})
 expect(uploaded.status()).toBe(201);const doc=await uploaded.json() as Doc;await open(page,doc)
 const raw=await page.evaluate(()=>{
  const spans=[...document.querySelectorAll<HTMLElement>('.pdf-page[data-page="1"] .textLayer span')]
  const first=spans.find(span=>span.textContent==='First exact source line')?.firstChild
  const second=spans.find(span=>span.textContent==='Second exact source line')?.firstChild
  if(!first || !second)throw new Error('Expected PDF.js line spans are missing')
  const range=document.createRange();range.setStart(first,0);range.setEnd(second,second.textContent!.length)
  const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range);return range.toString()
 })
 await page.waitForTimeout(150)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Multi-line exact source')
 const result=await save(page),note=await readNote(page,result.note.id)
 expect(note.sources[0].source.positions[0].textRanges.length).toBeGreaterThanOrEqual(2)
 expect(raw).toContain('First exact source line');expect(raw).toContain('Second exact source line')
 expect(note.sources[0].source.positions[0].textQuote).toBe('First exact source line\nSecond exact source line')
 await page.getByRole('button',{name:`查看原文：${doc.title}，PDF 第 1 页`,exact:true}).click()
 await expect(page.getByTestId('note-navigation-success')).toContainText('精确定位')
 await expectExactHighlight(page,1,2)
})

test('a legacy source without PDF.js ranges keeps reliable page navigation without a false highlight',async({page})=>{
 test.setTimeout(90000)
 const {docs}=await setup(page),doc=docs[0]!,raw=await select(page,2)
 await page.getByRole('button',{name:'添加到笔记',exact:true}).click();await chooseNew(page,'Legacy page-only source')
 const result=await save(page),note=await readNote(page,result.note.id)
 await page.route(`**/api/v1/notes/${note.id}`,async route=>{
  const response=await route.fetch(),body=await response.json()
  const sources=body.sources.map((block:any)=>({...block,source:{...block.source,positions:block.source.positions.map((position:any)=>{const {textRanges:_,...rest}=position;return rest})}}))
  await route.fulfill({response,json:{...body,sources}})
 })
 await page.reload();await showNote(page,note.title)
 await page.getByRole('button',{name:`查看原文：${doc.title}，PDF 第 2 页`,exact:true}).click()
 await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2')
 await expect(page.getByTestId('note-navigation-success')).toContainText('只能定位到页面')
 await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 expect((await readNote(page,note.id)).sources[0].originalText).toBe(raw)
})
