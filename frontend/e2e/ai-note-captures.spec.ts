import {test,expect,type Page} from '@playwright/test'
import {randomUUID} from 'node:crypto'
const origin='http://127.0.0.1:5182'
const modal=(page:Page)=>page.getByRole('dialog',{name:'保存到文献笔记',exact:true})
const headers=(token:string)=>({Origin:origin,'X-CSRF-Token':token})
async function setup(page:Page){
 const email=`mock-qa-${randomUUID()}@example.com`
 expect((await page.request.post('/api/v1/auth/register',{headers:{Origin:origin},data:{email,password:'Litera-test-123',displayName:'Isolated Mock QA'}})).status()).toBe(201)
 const login=await page.request.post('/api/v1/auth/login',{headers:{Origin:origin},data:{email,password:'Litera-test-123'}})
 expect(login.status()).toBe(200);const token=(await login.json()).csrfToken as string
 const pdf=await page.request.get('/api/v1/notes/mock-answers/fixture.pdf');expect(pdf.status()).toBe(200)
 const response=await page.request.post('/api/v1/documents',{headers:headers(token),multipart:{file:{name:'Isolated Mock QA.pdf',mimeType:'application/pdf',buffer:await pdf.body()}}});expect(response.status()).toBe(201)
 const doc=await response.json()
 await page.goto(`/reader/${doc.id}`)
 await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 return {token,doc,email}
}
async function preview(page:Page){
 const utility=page.getByRole('region',{name:'隔离模拟问答验收工具'})
 if(!await utility.getByRole('button',{name:'保存模拟引用回答到笔记'}).isVisible())await utility.getByRole('button',{name:'模拟问答保存验收（非真实AI）'}).click()
 await expect(utility.getByText('合成PDF核验引用（Mock）',{exact:true})).toBeVisible()
 return utility
}
async function capture(page:Page,uncited=false){
 const utility=await preview(page);await utility.getByRole('button',{name:uncited?'保存模拟无引用回答到笔记':'保存模拟引用回答到笔记',exact:true}).click()
 await expect(modal(page)).toBeVisible();await expect(modal(page).getByTestId('note-capture-answer')).toContainText('[MOCK]')
}
async function save(page:Page){
 const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/notes/captures')&&r.request().method()==='POST')
 await modal(page).getByRole('button',{name:'保存摘录',exact:true}).click();const result=await response
 expect([200,201],await result.text()).toContain(result.status());await expect(modal(page)).not.toBeVisible();return result.json()
}
async function note(page:Page,id:string){const r=await page.request.get('/api/v1/notes/'+id);expect(r.status()).toBe(200);return r.json()}

test('Mock cited answer: new/current note, immutable snapshot, dedup, draft, search, page navigation and persistence',async({page})=>{
 const {token,doc,email}=await setup(page);await capture(page)
 await modal(page).getByLabel('新笔记标题',{exact:true}).fill('Mock cited answer note')
 const result=await save(page);const first=await note(page,result.note.id)
 expect(first.sources).toHaveLength(1);expect(first.sources[0]).toMatchObject({kind:'ai_answer',answerRef:{provenance:'isolated_mock'},evidenceState:'verified',contextDocument:{documentId:doc.id},citations:[{pageNumber:1}]})
 await expect(page.getByTestId('ai-answer-note-block')).toContainText('非真实AI问答联调')
 await page.getByLabel('笔记正文',{exact:true}).fill('Unflushed draft is safely retained')
 // Opening the shared dialog flushes the existing auto-save controller.
 await capture(page)
 await expect(modal(page).getByRole('radio',{name:/当前笔记/})).toBeChecked()
 const duplicate=await save(page);expect(duplicate.deduplicated).toBe(true)
 expect((await note(page,first.id)).content).toBe('Unflushed draft is safely retained')
 expect((await note(page,first.id)).sources).toHaveLength(1)
 await page.getByLabel('搜索个人笔记关键词',{exact:true}).fill('artificial fixture')
 await expect(page.getByRole('region',{name:'笔记搜索结果'})).toContainText('AI回答')
 await page.getByRole('button',{name:'清空笔记搜索',exact:true}).click()
 await page.getByTestId('ai-answer-note-block').getByRole('button',{name:'查看引用原文',exact:true}).click()
 await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('1')
 await expect(page.getByTestId('source-highlight')).toHaveCount(0)
 await page.reload();await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染',{timeout:15000})
 if(!await page.getByLabel('文献笔记',{exact:true}).isVisible())await page.getByRole('button',{name:'笔记面板',exact:true}).click()
 const opener=page.getByRole('button',{name:'打开笔记：Mock cited answer note',exact:true});await expect(opener).toBeVisible();await opener.click()
 await expect(page.getByTestId('ai-answer-note-block')).toContainText('[MOCK]')
 expect((await note(page,first.id)).sources).toEqual(first.sources)
 expect((await page.request.post('/api/v1/auth/logout',{headers:headers(token)})).status()).toBe(204)
 await page.goto('/login');await page.getByLabel('邮箱',{exact:true}).fill(email);await page.getByLabel('密码',{exact:true}).fill('Litera-test-123');await page.getByRole('button',{name:'登录',exact:true}).click();await expect(page).toHaveURL('/library')
 expect((await note(page,first.id)).sources).toEqual(first.sources)
})

test('Mock uncited answer requires explicit confirmation and keeps no invented page',async({page})=>{
 await setup(page);await capture(page,true)
 await expect(modal(page).getByRole('button',{name:'保存摘录',exact:true})).toBeDisabled()
 await modal(page).getByLabel('我确认将无可信引用的AI回答保存为未核实内容',{exact:true}).check()
 const saved=await save(page)
 expect(saved.note.sources[0]).toMatchObject({evidenceState:'none',uncitedAcknowledged:true,citations:[]})
 await expect(page.getByTestId('ai-answer-note-block')).toContainText('未核实')
 await expect(page.getByTestId('ai-answer-note-block').getByRole('button',{name:'查看引用原文'})).toHaveCount(0)
})

test('other note, explicit association choice, network retry uses one operation and source failures cannot bypass verification',async({page})=>{
 const {token,doc}=await setup(page),otherId=randomUUID()
 const created=await page.request.post('/api/v1/notes',{headers:headers(token),data:{id:otherId,title:'Other personal note',content:'Retained personal body'}});expect(created.status()).toBe(201)
 await capture(page)
 await modal(page).getByRole('radio',{name:'其他已有笔记',exact:true}).check()
 await modal(page).getByRole('button',{name:'选择笔记：Other personal note',exact:true}).click()
 await modal(page).getByRole('radio',{name:'仅保存来源，不新增关联',exact:true}).check()
 let first=true;const operations:string[]=[]
 await page.route('**/api/v1/notes/captures',async route=>{
  operations.push(route.request().postDataJSON().operationId)
  if(first){first=false;await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'AI_ANSWER_UNAVAILABLE',message:'Simulated source service unavailable'}})});return}
  await route.continue()
 })
 await modal(page).getByRole('button',{name:'保存摘录',exact:true}).click()
 await expect(modal(page)).toContainText('Simulated source service unavailable')
 await modal(page).getByRole('button',{name:'重试保存',exact:true}).click();await expect(modal(page)).not.toBeVisible()
 expect(operations).toHaveLength(2);expect(operations[0]).toBe(operations[1])
 const stored=await note(page,otherId);expect(stored.sources).toHaveLength(1);expect(stored.documents).toHaveLength(0);expect(stored.content).toBe('Retained personal body')
 // A rejected evidence lookup offers no 'save unverified' bypass.
 await page.route('**/api/v1/notes/answer-preview/**',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({error:{code:'AI_EVIDENCE_INVALID',message:'Simulated evidence rejection'}})}))
 const utility=await preview(page);await utility.getByRole('button',{name:'保存模拟引用回答到笔记',exact:true}).click()
 await expect(modal(page)).toContainText('Simulated evidence rejection')
 await expect(modal(page).getByRole('button',{name:'保存摘录',exact:true})).toBeDisabled()
 await expect(modal(page).getByRole('checkbox')).toHaveCount(0)
 expect((await note(page,otherId)).sources).toHaveLength(1)
})
