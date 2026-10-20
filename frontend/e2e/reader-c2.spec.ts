import { test, expect, type Page } from '@playwright/test'
import { writeFileSync } from 'node:fs'
import { openLibrary, upload, origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
async function rendered(page:Page,n=1) { await expect(page.locator(`.pdf-page[data-page="${n}"]`)).toHaveAttribute('data-status','已渲染', {timeout:30000}) }
async function openMenu(page:Page) { await page.getByRole('button',{name:'管理已打开文献',exact:true}).click();await expect(page.locator('.workspace-manage-content')).toBeVisible() }
async function menuAction(page:Page,name:string) { await openMenu(page); await page.getByRole('button',{name,exact:true}).click() }
async function openTab(page:Page,id:string) { await page.locator(`[data-tab-id="${id}"] .document-title`).click() }
async function jump(page:Page,n:number) { await page.getByLabel('当前页码',{exact:true}).fill(String(n)); await page.getByLabel('当前页码',{exact:true}).press('Enter'); await rendered(page,n) }
test('C2 public navigation real host permissions source unavailable text position and teardown',async({page})=>{
  test.skip(process.env.LITERA_READER_PRODUCTION === '1', 'Dev-only module import; production UI is covered separately')
  const token=await openLibrary(page),a=await(await upload(page.request,token,readerPdf('Navigation A'),'Navigation A.pdf')).json(),b=await(await upload(page.request,token,readerPdf('Navigation B'),'Navigation B.pdf')).json()
  const comment=await(await page.request.post(`/api/v1/documents/${a.id}/annotations`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{commandId:crypto.randomUUID(),baseRevision:0,annotation:{type:'comment',pageNumber:1,geometry:{kind:'anchor',pageNumber:1,x:.2,y:.2},content:'Public annotation identity'}}})).json()
  await page.goto(`/reader/${a.id}`);await rendered(page)
  async function navigate(target:any){return page.evaluate(async target=>{const path='/src/reader/navigation.ts';const module=await import(path);return module.navigateReader(target)},target)}
  expect(await navigate({documentId:a.id,pageNumber:1,annotationId:comment.annotation.id})).toEqual({status:'ok'})
  await expect.poll(()=>page.evaluate(async()=>{const path='/src/reader/context.ts';return (await import(path)).readerContext.value?.annotationId})).toBe(comment.annotation.id)
  expect(await navigate({documentId:b.id,pageNumber:3,position:{pageNumber:3,textQuote:'Navigation B',rects:[{x:.1,y:.2,width:.2,height:.1}]}})).toEqual({status:'ok'})
  await expect(page).toHaveURL(`/reader/${b.id}`);await rendered(page,3)
  expect(await navigate({documentId:b.id,pageNumber:999})).toMatchObject({status:'error',code:'INVALID_PAGE'})
  expect(await navigate({documentId:b.id,pageNumber:3,annotationId:'missing'})).toMatchObject({code:'ANNOTATION_UNAVAILABLE'})
  expect(await navigate({documentId:b.id,pageNumber:3,extractionVersion:'v1',chunkId:'unconnected',quote:'test'})).toMatchObject({status:'unavailable',code:'SOURCE_UNAVAILABLE'})
  expect(await navigate({documentId:crypto.randomUUID(),pageNumber:1})).toMatchObject({status:'error'})
  await page.getByRole('link',{name:'文献管理',exact:true}).click()
  expect(await navigate({documentId:a.id,pageNumber:1})).toMatchObject({status:'unavailable',code:'READER_UNAVAILABLE'})
})
test('C2 shared menu list, overflow, adjacent/last close and independent panel/read state',async({page})=>{
  const token=await openLibrary(page), docs=[]
  for(let i=0;i<4;i++) docs.push(await(await upload(page.request,token,readerPdf('Workspace '+i,7),`Workspace ${i} long research document title.pdf`)).json())
  await page.reload()
  for(const doc of docs) { await page.locator('tbody .document-title').filter({hasText:doc.title}).click(); await rendered(page); await page.getByRole('link',{name:'文献管理',exact:true}).click() }
  await openTab(page,docs[0].id); await rendered(page)
  await page.locator('.reader-view-select').click();await page.getByRole('option',{name:'单页切换',exact:true}).click();await jump(page,4)
  await page.getByLabel('缩放比例',{exact:true}).fill('175');await page.getByLabel('缩放比例',{exact:true}).press('Enter');await rendered(page,4)
  await page.getByRole('button',{name:'展开文献导航',exact:true}).click();await page.getByRole('button',{name:'大纲',exact:true}).click()
  await page.getByRole('button',{name:'搜索文献',exact:true}).click()
  await openTab(page,docs[1].id);await rendered(page); await openMenu(page)
  await expect(page.locator('.workspace-open-list > div')).toHaveCount(4)
  await expect(page.locator('.workspace-open-list [aria-current="page"]')).toContainText(docs[1].title)
  await page.screenshot({path:'../.cache/c2-menu-desktop.png',animations:'disabled'})
  await page.getByRole('button',{name:`从列表关闭：${docs[2].title}`,exact:true}).click();await expect(page.locator('.reader-tab')).toHaveCount(3)
  await page.getByRole('button',{name:`从列表关闭：${docs[1].title}`,exact:true}).click();await rendered(page);await expect(page).toHaveURL(`/reader/${docs[3].id}`)
  await expect(page.locator('.reader-tab')).toHaveCount(2)
  await page.locator('.workspace-open-list button').filter({hasText:docs[0].title}).click(); await rendered(page,4)
  await expect(page.getByLabel('缩放比例',{exact:true})).toHaveValue('175');await expect(page.getByRole('button',{name:'大纲',exact:true})).toHaveClass(/selected/)
  await expect(page.getByLabel('PDF 文内搜索',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'关闭搜索',exact:true}).click();await page.getByRole('button',{name:'收起文献导航',exact:true}).click()
  await page.setViewportSize({width:390,height:844});await openMenu(page)
  await page.screenshot({path:'../.cache/c2-menu-narrow.png',animations:'disabled'})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  await page.getByRole('button',{name:'关闭其他文献',exact:true}).click();await expect(page.locator('.reader-tab')).toHaveCount(1)
  await page.setViewportSize({width:1366,height:768});await menuAction(page,'关闭当前文献');await expect(page).toHaveURL('/library');await expect(page.locator('.reader-tab')).toHaveCount(0)
})
test('C2 batch close stops on editing, unknown save, conflict and inactive retained draft',async({page})=>{
  const token=await openLibrary(page), a=await(await upload(page.request,token,readerPdf('Draft A',2),'Draft A.pdf')).json(), b=await(await upload(page.request,token,readerPdf('Draft B',2),'Draft B.pdf')).json()
  await page.reload();await page.locator('tbody .document-title').filter({hasText:b.title}).click();await rendered(page);await page.getByRole('link',{name:'文献管理',exact:true}).click();await page.locator('tbody .document-title').filter({hasText:a.title}).click();await rendered(page)
  await page.getByRole('button',{name:'批注',exact:true}).click();await page.getByRole('button',{name:'注释',exact:true}).click();await page.locator('.annotation-overlay').first().click({position:{x:180,y:220}});await page.getByLabel('批注正文',{exact:true}).fill('不能丢失的草稿')
  await menuAction(page,'关闭全部文献');await expect(page).toHaveURL(`/reader/${a.id}`);await expect(page.getByLabel('批注正文',{exact:true})).toHaveValue('不能丢失的草稿')
  await page.mouse.click(10,180)
  let reject=true
  await page.route(`**/documents/${a.id}/annotations`,async route=>{if(route.request().method()==='POST'&&reject) await route.abort();else await route.continue()})
  await page.getByRole('button',{name:'保存批注',exact:true}).click();await expect(page.locator('.annotation-error')).toContainText('未保存')
  await menuAction(page,'关闭全部文献');await expect(page.locator('.reader-tab')).toHaveCount(1);await expect(page).toHaveURL(`/reader/${a.id}`)
  await page.mouse.click(10,180);await page.getByRole('button',{name:'保留批注草稿并返回文献库',exact:true}).click();await expect(page).toHaveURL('/library')
  await menuAction(page,'关闭全部文献');await expect(page).toHaveURL(`/reader/${a.id}`);await expect(page.locator('.reader-tab')).toHaveCount(1)
  await expect(page.locator('.annotation-error')).toContainText('未完成的批注草稿')
  reject=false;await page.mouse.click(10,180);await page.getByRole('button',{name:'重试保存批注',exact:true}).click();await expect.poll(async()=> (await(await page.request.get(`/api/v1/documents/${a.id}/annotations`)).json()).items.length).toBe(1)
  await menuAction(page,'关闭全部文献');await expect(page).toHaveURL('/library')
})
test('C2 batch close never loses a committed in-flight response or a real CAS conflict',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Inflight CAS',2),'Inflight CAS.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page)
  let release!:()=>void, committed=false
  const held=new Promise<void>(resolve=>{release=resolve})
  await page.route(`**/documents/${doc.id}/annotations`,async route=>{
    if(route.request().method()!=='POST'){await route.continue();return}
    const response=await route.fetch();committed=true;await held;await route.fulfill({response})
  })
  async function draft(text:string){await page.getByRole('button',{name:'批注',exact:true}).click();await page.getByRole('button',{name:'注释',exact:true}).click();await page.locator('.annotation-overlay').first().click({position:{x:180,y:220}});await page.getByLabel('批注正文',{exact:true}).fill(text);await page.getByRole('button',{name:'保存批注',exact:true}).click()}
  await draft('已提交但响应仍在途');await expect.poll(()=>committed).toBe(true)
  await menuAction(page,'关闭全部文献');await expect(page).toHaveURL(`/reader/${doc.id}`);await expect(page.locator('.reader-tab')).toHaveCount(1)
  release();await expect(page.getByLabel('批注正文',{exact:true})).toHaveCount(0);await page.unroute(`**/documents/${doc.id}/annotations`)
  expect((await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).items).toHaveLength(1)
  await page.mouse.click(10,180)
  const external=await page.request.post(`/api/v1/documents/${doc.id}/annotations`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{commandId:crypto.randomUUID(),baseRevision:1,annotation:{type:'comment',pageNumber:1,geometry:{kind:'anchor',pageNumber:1,x:.4,y:.4},content:'另一端版本'}}})
  expect(external.status()).toBe(201)
  await draft('本地冲突草稿');await expect(page.locator('.annotation-error')).toContainText('并发冲突')
  await menuAction(page,'关闭全部文献');await expect(page).toHaveURL(`/reader/${doc.id}`);await expect(page.locator('.reader-tab')).toHaveCount(1)
  expect((await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).items).toHaveLength(2)
  expect(await page.evaluate(id=>Object.keys(sessionStorage).some(key=>key.startsWith('litera:annotations:')&&key.endsWith(':'+id)),doc.id)).toBe(true)
})
test('C2 long PDF 1000 pages, DPR2 500%, ten tabs repeated cycles and actual release metrics',async({page,browser})=>{
  test.setTimeout(240000)
  const token=await openLibrary(page),docs=[]
  for(let i=0;i<10;i++) docs.push(await(await upload(page.request,token,readerPdf('Stress '+i,i===0?1000:12,true,{split:true,detail:true}),`Stress ${i}.pdf`)).json())
  const context=await browser.newContext({baseURL:origin,viewport:{width:1366,height:768},deviceScaleFactor:2,storageState:await page.context().storageState()})
  const reader=await context.newPage(),cdp=await context.newCDPSession(reader),metrics:any[]=[]
  console.log('C2 Chromium version',browser.version())
  await reader.addInitScript(()=>{
    const Original=window.Worker;(window as any).workerCounts={created:0,live:0,peak:0}
    window.Worker=class extends Original { constructor(...args:ConstructorParameters<typeof Worker>){super(...args);const s=(window as any).workerCounts;s.created++;s.live++;s.peak=Math.max(s.peak,s.live)} override terminate(){(window as any).workerCounts.live--;super.terminate()} }
  })
  // SPA route changes do not reset Playwright's already-achieved networkidle state.
  // Let the existing 100ms render debounce and popover transitions finish before GC.
  async function sample(label:string){await reader.waitForLoadState('networkidle');await reader.waitForTimeout(350);await cdp.send('HeapProfiler.collectGarbage');const heap=await cdp.send('Runtime.getHeapUsage');const dom=await cdp.send('Memory.getDOMCounters');const state=await reader.evaluate(()=>({workers:(window as any).workerCounts,canvas:[...document.querySelectorAll('canvas')].reduce((n,c)=>n+c.width*c.height*4,0),painted:[...document.querySelectorAll('.pdf-page canvas')].filter(c=>(c as HTMLCanvasElement).width>0).length}));const result={label,heap:heap.usedSize,dom,...state};metrics.push(result);return result}
  try{
    await reader.goto('/library');await sample('library-baseline')
    const start=Date.now();await reader.locator('tbody .document-title').filter({hasText:docs[0].title}).click();await rendered(reader);metrics.push({label:'1000-page-first-frame',ms:Date.now()-start})
    await jump(reader,750);await reader.getByRole('button',{name:'展开文献导航',exact:true}).click();await sample('1000-page-navigation')
    await reader.getByRole('button',{name:'搜索文献',exact:true}).click();const searching=Date.now();await reader.getByLabel('PDF 文内搜索',{exact:true}).fill('international');await expect(reader.locator('.pdf-search [role="status"]')).toContainText('1000 个匹配',{timeout:60000});metrics.push({label:'1000-page-search',ms:Date.now()-searching})
    await reader.locator('.reader-view-select').click();await reader.getByRole('option',{name:'单页切换',exact:true}).click();await jump(reader,3)
    await reader.getByLabel('缩放比例',{exact:true}).fill('500');await reader.getByLabel('缩放比例',{exact:true}).press('Enter');await rendered(reader,3)
    await expect(reader.locator('.pdf-page[data-page="3"] .pdf-resolution-hint')).toHaveCount(1)
    await reader.locator('.pdf-page[data-page="3"] .textLayer span').filter({hasText:'Stress 0'}).first().scrollIntoViewIfNeeded()
    const high=await sample('DPR2-500-percent');expect(high.canvas).toBeLessThan(80*1024*1024)
    await reader.screenshot({path:'../.cache/c2-high-dpr.png'})
    await reader.getByRole('link',{name:'文献管理',exact:true}).click()
    for(const doc of docs.slice(1)){await reader.locator('tbody .document-title').filter({hasText:doc.title}).click();await rendered(reader);await reader.getByRole('link',{name:'文献管理',exact:true}).click()}
    await expect(reader.locator('.reader-tab')).toHaveCount(10)
    for(let cycle=0;cycle<3;cycle++){
      for(const doc of docs){await openMenu(reader);await reader.locator('.workspace-open-list button').filter({hasText:doc.title}).click();await rendered(reader,doc===docs[0]?3:1)}
      const active=await sample('active-cycle-'+cycle);expect(active.workers.live).toBe(1)
      await reader.getByRole('link',{name:'文献管理',exact:true}).click();const released=await sample('released-cycle-'+cycle);expect(released.workers.live).toBe(0);expect(released.canvas).toBe(0)
    }
    await menuAction(reader,'关闭全部文献');await expect(reader.locator('.reader-tab')).toHaveCount(0);await sample('closed-all')
    writeFileSync('../.cache/c2-performance.json',JSON.stringify(metrics,null,2))
  }finally{await context.close()}
})
