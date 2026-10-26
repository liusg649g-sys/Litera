import {test,expect,type Page} from '@playwright/test'
import {randomUUID} from 'node:crypto'
import {readerPdf} from './reader-fixtures'
const origin='http://127.0.0.1:5182'
const headers=(token:string)=>({Origin:origin,'X-CSRF-Token':token})
async function showNote(page:Page,title:string){
 await expect(page.locator('.pdf-page[data-status="已渲染"]').first()).toBeVisible({timeout:15000})
 if(!await page.getByLabel('文献笔记',{exact:true}).isVisible())await page.getByRole('button',{name:'笔记面板',exact:true}).click()
 const button=page.getByRole('button',{name:'打开笔记：'+title,exact:true});await expect(button).toBeVisible();await button.click()
 await expect(page.getByLabel('笔记标题',{exact:true})).toHaveValue(title)
}
async function readNote(page:Page,id:string){const response=await page.request.get('/api/v1/notes/'+id);expect(response.status()).toBe(200);return response.json()}

test('source survives trash/restore/purge and identical PDF reupload never relabels its immutable source (temporary SQLite/PDF.js)',async({page})=>{
 const email=`e1-life-${randomUUID()}@example.com`,password='Litera-test-123'
 expect((await page.request.post('/api/v1/auth/register',{headers:{Origin:origin},data:{email,password,displayName:'E1 temporary lifecycle'}})).status()).toBe(201)
 const login=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password}});expect(login.status()).toBe(200)
 const token=(await login.json()).csrfToken as string,aBytes=readerPdf('E1 original A',3)
 async function upload(bytes:Buffer,name:string){const response=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name,mimeType:'application/pdf',buffer:bytes}}});expect(response.status()).toBe(201);return response.json()}
 const a=await upload(aBytes,'Lifecycle Source A.pdf'),b=await upload(readerPdf('E1 independent B',2),'Lifecycle B.pdf')
 await page.goto('/reader/'+a.id)
 await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 await page.getByLabel('当前页码',{exact:true}).fill('2');await page.getByLabel('当前页码',{exact:true}).press('Enter')
 await expect(page.locator('.pdf-page[data-page="2"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 await page.evaluate(()=>{
  const span=[...document.querySelectorAll<HTMLElement>('.pdf-page[data-page="2"] .textLayer span')].find(s=>s.textContent?.trim())!,node=span.firstChild!
  const range=document.createRange();range.setStart(node,0);range.setEnd(node,node.textContent!.length)
  const selection=window.getSelection()!;selection.removeAllRanges();selection.addRange(range)
 })
 const capture=page.getByRole('button',{name:'添加到笔记',exact:true});await expect(capture).toBeEnabled();await capture.click()
 const dialog=page.getByRole('dialog',{name:'保存到文献笔记',exact:true}),title='E1 persistent source note'
 await dialog.getByLabel('新笔记标题',{exact:true}).fill(title)
 const captured=page.waitForResponse(r=>r.url().endsWith('/api/v1/notes/captures')&&r.request().method()==='POST')
 await dialog.getByRole('button',{name:'保存摘录',exact:true}).click();const response=await captured;expect(response.status()).toBe(201)
 const initial=(await response.json()).note,id=initial.id,sources=initial.sources
 await expect(dialog).not.toBeVisible()
 await page.getByLabel('笔记正文',{exact:true}).fill('Persistent personal thoughts')
 await expect.poll(async()=>(await readNote(page,id)).content).toBe('Persistent personal thoughts')
 expect((await page.request.put(`/api/v1/notes/${id}/documents/${b.id}`,{headers:headers(token)})).status()).toBe(200)
 await page.reload();await showNote(page,title)
 async function openB(){
  await page.getByRole('region',{name:'关联文献',exact:true}).getByRole('button',{name:'打开关联文献：'+b.title,exact:true}).click()
  await expect(page).toHaveURL('/reader/'+b.id);await expect(page.getByLabel('笔记标题',{exact:true})).toHaveValue(title)
 }
 await openB()
 expect((await page.request.delete('/api/v1/documents/'+a.id,{headers:headers(token)})).status()).toBe(204)
 await page.reload();await showNote(page,title)
 const source=page.getByRole('button',{name:`查看原文：${a.title}，PDF 第 2 页`,exact:true})
 await source.click();await expect(page.getByTestId('note-navigation-error')).toContainText('无法可靠定位来源')
 await expect(page).toHaveURL('/reader/'+b.id);await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 expect((await readNote(page,id)).sources).toEqual(sources)
 expect((await page.request.post('/api/v1/trash/documents/'+a.id+'/restore',{headers:headers(token)})).status()).toBe(200)
 await page.reload();await showNote(page,title);await source.click()
 await expect(page).toHaveURL('/reader/'+a.id);await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2')
 await expect(page.getByTestId('source-highlight').first()).toBeVisible({timeout:15000})
 await expect(page.getByLabel('笔记正文',{exact:true})).toHaveValue('Persistent personal thoughts')
 await openB();await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 expect((await page.request.delete('/api/v1/documents/'+a.id,{headers:headers(token)})).status()).toBe(204)
 expect((await page.request.delete('/api/v1/trash/documents/'+a.id,{headers:headers(token)})).status()).toBe(204)
 const replacement=await upload(aBytes,'Lifecycle Source A.pdf');expect(replacement.id).not.toBe(a.id);expect(replacement.attachment.sha256).toBe(a.attachment.sha256)
 await page.reload();await showNote(page,title);await source.click()
 await expect(page.getByTestId('note-navigation-error')).toContainText('无法可靠定位来源');await expect(page).toHaveURL('/reader/'+b.id)
 const after=await readNote(page,id);expect(after.sources).toEqual(sources);expect(after.documents.map((d:{id:string})=>d.id)).toEqual([b.id])
 expect(after.sources[0].source.documentId).toBe(a.id);expect(after.sources[0].source.pageNumber).toBe(2)
 expect((await page.request.get('/api/v1/documents/'+a.id)).status()).toBe(404)
 await expect(page.getByTestId('source-highlight')).toHaveCount(0)
})
