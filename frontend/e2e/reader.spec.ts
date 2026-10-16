import { test, expect } from '@playwright/test'
import { openLibrary, session, upload, origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
import { readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
async function rendered(page: import('@playwright/test').Page, number:number) {
  await expect(page.locator(`[data-page="${number}"]`)).toHaveAttribute('data-status','已渲染')
}
async function view(page:import('@playwright/test').Page, name:string) {
  await page.locator('.reader-view-select').click(); await page.getByRole('option',{name,exact:true}).click()
}
async function jump(page:import('@playwright/test').Page,n:number) { await page.getByLabel('当前页码',{exact:true}).fill(String(n)); await page.getByLabel('当前页码',{exact:true}).press('Enter') }

test('real upload → local Worker/Canvas/text selection, views, navigation and original download; real progress',async({page})=>{
  const token=await openLibrary(page), bytes=readerPdf('Research reading',7,true)
  const doc=await(await upload(page.request,token,bytes,'真实阅读测试.pdf')).json()
  const workers:string[]=[],failed:string[]=[],writes:string[]=[]
  page.on('worker',w=>workers.push(w.url()))
  page.on('pageerror',e=>failed.push(e.message))
  page.on('request',r=>{if(r.method()!=='GET'&&r.url().includes('/documents/'))writes.push(r.url())})
  await page.reload(); await page.locator('tbody .document-title').first().click()
  await expect(page).toHaveURL(`/reader/${doc.id}`); await rendered(page,1)
  expect(workers.some(url=>url.includes('pdf.worker'))).toBe(true)
  await expect(page.locator('[data-page="1"] .textLayer')).toContainText('Research reading - Page 1')
  await expect(page.locator('[data-page="1"] .textLayer')).toContainText('科研文献阅读测试')
  // Actual mouse text selection; Chromium copies the selected PDF text via native selection.
  const span=page.locator('[data-page="1"] .textLayer span').filter({hasText:'Research reading'}).first()
  const box=(await span.boundingBox())!
  await page.mouse.move(box.x+1,box.y+box.height/2); await page.mouse.down(); await page.mouse.move(box.x+box.width-1,box.y+box.height/2,{steps:15}); await page.mouse.up()
  expect(await page.evaluate(()=>getSelection()?.toString())).toContain('Research reading')
  await page.context().grantPermissions(['clipboard-read','clipboard-write'])
  await page.keyboard.press('Control+c')
  expect(await page.evaluate(()=>navigator.clipboard.readText())).toContain('Research reading')
  const painted=await page.locator('[data-page="1"] canvas').evaluate((canvas:HTMLCanvasElement)=>{
    const pixels=canvas.getContext('2d')!.getImageData(0,0,canvas.width,canvas.height).data
    for(let i=0;i<pixels.length;i+=4)if(pixels[i]!<180&&pixels[i+1]!<180&&pixels[i+2]!<180)return true
    return false
  }); expect(painted).toBe(true)
  await jump(page,4); await rendered(page,4)
  await view(page,'单页切换'); await rendered(page,4); await expect(page.locator('.pdf-page')).toHaveCount(1)
  await page.getByRole('button',{name:'下一页',exact:true}).click(); await rendered(page,5)
  await view(page,'双页并排'); await rendered(page,5); await expect(page.locator('.pdf-page')).toHaveCount(2)
  await page.getByRole('button',{name:'下一页',exact:true}).click(); await rendered(page,7)
  await expect(page.locator('.pdf-page')).toHaveCount(1); await expect(page.getByRole('button',{name:'下一页',exact:true})).toBeDisabled()
  await page.getByLabel('PDF 阅读区域',{exact:true}).focus(); await page.keyboard.press('ArrowLeft'); await rendered(page,5)
  await jump(page,999); await expect(page.getByRole('status')).toContainText('请输入 1–7')
  const downloading=page.waitForEvent('download');await page.getByRole('link',{name:'下载原始 PDF'}).click();const download=await downloading
  expect(readFileSync((await download.path())!)).toEqual(bytes)
  await expect.poll(async()=> (await(await page.request.get(`/api/v1/documents/${doc.id}/progress`)).json()).pageNumber).toBe(5)
  const progress=await(await page.request.get(`/api/v1/documents/${doc.id}/progress`)).json();expect(progress.zoom).toBeGreaterThanOrEqual(.5)
  const partial=await page.request.get(`/api/v1/documents/${doc.id}/content`,{headers:{Range:'bytes=0-99'}})
  expect(partial.status()).toBe(206);expect(await partial.body()).toEqual(bytes.subarray(0,100))
  expect((await page.request.get(`/api/v1/documents/${doc.id}/content`,{headers:{Range:'bytes=999999-'}})).status()).toBe(416)
  expect(writes.length).toBeGreaterThan(0);expect(writes.every(url=>url===`http://127.0.0.1:5175/api/v1/documents/${doc.id}/progress`)).toBe(true);expect(failed).toEqual([])
  await page.screenshot({path:'test-results/reader/desktop.png'})
})

test('Tool groups are enabled and responsive panels preserve reading',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('layout',1))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page,1)
  const writes:string[]=[];page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url())})
  await page.getByRole('button',{name:'批注',exact:true}).click()
  await expect(page.getByRole('button',{name:/荧光笔/})).toHaveCount(0)
  await expect(page.locator('.reader-secondary > button.el-tooltip__trigger')).toHaveCount(7)
  for (const name of ['高亮','下划线','波浪线','删除线','注释','自由文本']) {
    await expect(page.getByRole('button',{name,exact:true})).toHaveAttribute('aria-disabled','false')
  }
  for(const [group,tool] of [['形状','矩形'],['插入','签名'],['批注','手绘']]){
    await page.getByRole('button',{name:group,exact:true}).click()
    const button=page.getByRole('button',{name:tool,exact:true})
    await expect(button).toHaveAttribute('aria-disabled','false');await button.click()
    if(tool==='签名')await page.getByLabel('创建视觉签名').getByRole('button',{name:'× 取消',exact:true}).click()
  }
  await page.getByRole('button',{name:'阅读',exact:true}).click()
  for(const size of [{width:1920,height:1080},{width:1366,height:768},{width:390,height:844}]){
    await page.setViewportSize(size)
    await page.getByRole('button',{name:'展开文献导航',exact:true}).click()
    await expect(page.getByRole('button',{name:'缩略图第 1 页',exact:true})).toBeVisible()
    await page.getByRole('button',{name:'关闭文献导航',exact:true}).click()
    await page.getByRole('button',{name:'搜索文献',exact:true}).click()
    await expect(page.getByLabel('PDF 文内搜索',{exact:true})).toBeVisible()
    if(size.width<1100){await expect(page.getByRole('dialog',{name:'搜索',exact:true})).toBeVisible();await page.keyboard.press('Escape')}
    else await page.getByRole('button',{name:'关闭搜索',exact:true}).click()
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
    await page.screenshot({path:`test-results/reader/layout-${size.width}.png`})
  }
  expect(writes.every(url=>url.endsWith('/progress'))).toBe(true)
})

test('A/B/A tabs keep page/view, deduplicate and terminate real workers on switch/leave',async({page})=>{
  await page.addInitScript(()=>{
    const Native=window.Worker
    const stats={created:0,terminated:0};Object.assign(window,{readerWorkerStats:stats})
    window.Worker=class extends Native{constructor(url:string|URL,options?:WorkerOptions){super(url,options);stats.created++} override terminate(){stats.terminated++;super.terminate()}}
  })
  const token=await openLibrary(page)
  const a=await(await upload(page.request,token,readerPdf('Paper A'),'A.pdf')).json(), b=await(await upload(page.request,token,readerPdf('Paper B',1),'B.pdf')).json()
  await page.goto(`/reader/${a.id}`);await rendered(page,1);await view(page,'单页切换');await jump(page,4);await rendered(page,4)
  await page.getByRole('link',{name:'返回文献库',exact:true}).click()
  const bRow=page.locator('tbody tr').filter({has:page.getByRole('button',{name:'B',exact:true})})
  await bRow.locator('.document-title').click();await rendered(page,1)
  await page.locator('.reader-tab').filter({hasText:'A'}).getByRole('button',{name:'A',exact:true}).click();await rendered(page,4)
  await expect(page.locator('.textLayer')).toContainText('Paper A - Page 4');await expect(page.locator('.reader-tab')).toHaveCount(2)
  for(let i=0;i<3;i++){
    await page.locator('.reader-tab').getByRole('button',{name:'B',exact:true}).click()
    await page.locator('.reader-tab').getByRole('button',{name:'A',exact:true}).click();await rendered(page,4)
  }
  expect(await page.locator('.pdf-page canvas').count()).toBe(1)
  await page.getByRole('link',{name:'返回文献库',exact:true}).click()
  await expect.poll(()=>page.evaluate(()=>{const s=(window as any).readerWorkerStats;return s.created-s.terminated})).toBe(0)
  expect(await page.locator('.textLayer').count()).toBe(0)
})

test('protected failures, actual corrupt stored PDF, retry and one bounded 416 fallback',async({page,browser})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('fault'))).json()
  const other=await browser.newContext({baseURL:origin});await session(other.request)
  const stranger=await other.newPage();await stranger.goto(`/reader/${doc.id}`)
  await expect(stranger.getByRole('alert')).toContainText('无权访问');await expect(stranger.locator('canvas')).toHaveCount(0);await other.close()
  let count=0
  await page.route(`**/documents/${doc.id}/content`,async route=>{
    count++;if(count===1)await route.fulfill({status:416,contentType:'application/json',body:JSON.stringify({error:{code:'INVALID_RANGE',message:'range fault'}})})
    else await route.continue()
  })
  await page.goto(`/reader/${doc.id}`);await rendered(page,1);expect(count).toBe(2)
  await page.unroute(`**/documents/${doc.id}/content`)
  // Read only the disposable test server's manifest, then corrupt its real private file.
  const manifest=JSON.parse(readFileSync('test-results/e2e-storage.json','utf8'))
  // Files are located by the independent test-only manifest after upload.
  const { execFileSync }=await import('node:child_process')
  const stored=execFileSync('..\\backend\\.venv\\Scripts\\python.exe',['-c',`import sqlite3; c=sqlite3.connect(${JSON.stringify(manifest.database)}); print(c.execute('select storage_key from document_files where document_id=?',(${JSON.stringify(doc.id)},)).fetchone()[0])`],{encoding:'utf8'}).trim()
  const file=join(manifest.pdfRoot,stored),original=readFileSync(file)
  try{
    writeFileSync(file,Buffer.from('%PDF-1.7\ncorrupt stored file'))
    await page.reload();await expect(page.getByRole('alert')).toContainText('PDF 结构损坏')
    writeFileSync(file,original);await page.getByRole('button',{name:'重试加载',exact:true}).click();await rendered(page,1)
  }finally{writeFileSync(file,original)}
  await page.request.post('/api/v1/auth/logout',{headers:{Origin:origin,'X-CSRF-Token':token}})
  await view(page,'单页切换');await page.getByRole('link',{name:'返回文献库',exact:true}).click()
  await expect(page).toHaveURL('/login')
})


test('network retry, real content 404 after soft delete, and real content 401 after session revocation',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('protected-stream',1))).json()
  const content=`**/documents/${doc.id}/content`
  await page.route(content,route=>route.abort())
  await page.goto(`/reader/${doc.id}`);await expect(page.getByRole('alert')).toContainText('无法加载 PDF')
  expect((await(await page.request.get(`/api/v1/documents/${doc.id}/progress`)).json()).version).toBe(0)
  await page.unroute(content)
  await page.getByRole('button',{name:'重试加载',exact:true}).click();await rendered(page,1)
  await page.route(content,async route=>{
    await page.request.delete(`/api/v1/documents/${doc.id}`,{headers:{Origin:origin,'X-CSRF-Token':token}})
    await route.continue()
  })
  await page.reload();await expect(page.getByRole('alert')).toContainText('已删除或无权访问')
  await page.unroute(content)
  await page.request.post(`/api/v1/trash/documents/${doc.id}/restore`,{headers:{Origin:origin,'X-CSRF-Token':token}})
  await page.getByRole('button',{name:'重试加载',exact:true}).click();await rendered(page,1)
  await page.route(content,async route=>{
    await page.request.post('/api/v1/auth/logout',{headers:{Origin:origin,'X-CSRF-Token':token}})
    await route.continue()
  })
  await page.reload();await expect(page).toHaveURL('/login');await expect(page.locator('.pdf-page')).toHaveCount(0)
})

test('continuous scrolling updates current page and releases distant Canvas buffers',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('long-document',40))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page,1)
  await jump(page,30);await rendered(page,30)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('30')
  await expect.poll(()=>page.locator('[data-page="1"] canvas').evaluate((c:HTMLCanvasElement)=>c.width)).toBe(0)
  const buffers=await page.locator('.pdf-page canvas').evaluateAll(elements=>{
    const canvases=elements as HTMLCanvasElement[]
    return {active:canvases.filter(c=>c.width>0).length,bytes:canvases.reduce((n,c)=>n+c.width*c.height*4,0)}
  })
  expect(buffers.active).toBeLessThan(8);expect(buffers.bytes).toBeLessThan(192*1024*1024)
  console.log('A1 observed Canvas buffers',JSON.stringify(buffers))
  await page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(element=>{element.scrollTop+=element.querySelector('[data-page="30"]')!.getBoundingClientRect().height+20})
  await expect.poll(()=>page.getByLabel('当前页码',{exact:true}).inputValue()).not.toBe('30')
})

test('mixed page CropBox and intrinsic rotation share Canvas/text coordinates at DPR2',async({page,browser})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('rotated-crop',7,true))).json()
  const context=await browser.newContext({baseURL:origin,deviceScaleFactor:2,viewport:{width:1366,height:768},storageState:await page.context().storageState()})
  try{
    const reader=await context.newPage();await reader.goto(`/reader/${doc.id}`);await rendered(reader,1)
    await view(reader,'单页切换');await jump(reader,3);await rendered(reader,3)
    await reader.getByLabel('缩放比例',{exact:true}).fill('100');await reader.getByLabel('缩放比例',{exact:true}).press('Enter');await rendered(reader,3)
    const pageBox=reader.locator('[data-page="3"]'),canvas=pageBox.locator('canvas')
    await expect(pageBox).toHaveCSS('width','740px');await expect(pageBox).toHaveCSS('height','580px')
    expect(await canvas.evaluate((c:HTMLCanvasElement)=>[c.width,c.height])).toEqual([1480,1160])
    const text=pageBox.locator('.textLayer span').filter({hasText:'rotated-crop'}).first()
    const textBounds=(await text.boundingBox())!,paperBounds=(await pageBox.boundingBox())!
    expect(textBounds.x).toBeGreaterThanOrEqual(paperBounds.x-1);expect(textBounds.x+textBounds.width).toBeLessThanOrEqual(paperBounds.x+paperBounds.width+1)
    await expect(pageBox.locator('.textLayer')).toContainText('科研文献阅读测试')
  }finally{await context.close()}
})

test('module Worker with incorrect MIME reports deployment error and recovers after reload',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('worker-mime',1))).json()
  const worker='**/*pdf.worker*.mjs*'
  await page.route(worker,async route=>{
    const response=await route.fetch()
    await route.fulfill({response,headers:{...response.headers(),'content-type':'application/octet-stream','x-content-type-options':'nosniff'}})
  })
  await page.goto(`/reader/${doc.id}`)
  await expect(page.getByRole('alert')).toContainText('PDF 阅读组件启动失败')
  await page.unroute(worker)
  await page.getByRole('button',{name:'重试加载',exact:true}).click()
  await rendered(page,1)
})
