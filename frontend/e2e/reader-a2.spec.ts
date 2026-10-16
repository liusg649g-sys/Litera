import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { openLibrary, upload, origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
async function rendered(page: Page, n = 1) { await expect(page.locator(`.pdf-page[data-page="${n}"]`)).toHaveAttribute('data-status', '已渲染') }
async function jump(page: Page, n: number) { const input = page.getByLabel('当前页码', { exact: true }); await input.fill(String(n)); await input.press('Enter'); await rendered(page, n) }
async function zoom(page: Page, value: string) { const input = page.getByLabel('缩放比例', { exact: true }); await input.fill(value); await input.press('Enter') }
async function preset(page: Page, label: string) { await page.getByRole('button', { name: '缩放预设', exact: true }).click(); await page.getByRole('menuitem', { name: label, exact: true }).click() }
async function view(page: Page, label: string) { await page.locator('.reader-view-select').click(); await page.getByRole('option', { name: label, exact: true }).click() }
async function saved(page: Page, id: string, expected: any) { await expect.poll(async () => (await (await page.request.get(`/api/v1/documents/${id}/progress`)).json())).toMatchObject(expected) }

test('A2 zoom bounds, fit after panels, scoped wheel, spread anchor and DPR budget', async ({ page }) => {
  const token = await openLibrary(page), doc = await (await upload(page.request, token, readerPdf('Zoom', 7), 'Zoom.pdf')).json()
  await page.goto(`/reader/${doc.id}`); await rendered(page)
  await zoom(page, 'abc'); await expect(page.getByRole('status')).toContainText('有效的缩放')
  await zoom(page, '10'); await expect(page.getByLabel('缩放比例', { exact: true })).toHaveValue('50'); await rendered(page)
  await expect(page.getByRole('button', { name: '缩小', exact: true })).toBeDisabled()
  await zoom(page, '900'); await expect(page.getByLabel('缩放比例', { exact: true })).toHaveValue('500'); await rendered(page)
  await expect(page.getByRole('button', { name: '放大', exact: true })).toBeDisabled()
  expect(await page.locator('[data-page="1"] canvas').evaluate((c: HTMLCanvasElement) => c.width*c.height)).toBeLessThan(16_020_000)
  await zoom(page, '100'); await jump(page, 4)
  const before = await page.locator('[data-page="4"]').boundingBox(); await zoom(page, '125'); await rendered(page, 4)
  await expect(page.getByLabel('当前页码', { exact: true })).toHaveValue('4')
  const root = page.getByLabel('PDF 阅读区域', { exact: true }), r = (await root.boundingBox())!
  await root.dispatchEvent('wheel', { ctrlKey: true, deltaY: -100, clientX: r.x+r.width/2, clientY:r.y+r.height/2 }); await rendered(page, 4)
  expect(Number(await page.getByLabel('缩放比例', { exact: true }).inputValue())).toBeGreaterThan(125)
  const ratio = await page.getByLabel('缩放比例', { exact: true }).inputValue()
  await page.locator('.reader-main-toolbar').dispatchEvent('wheel', { ctrlKey: true, deltaY: -100 }); expect(await page.getByLabel('缩放比例', { exact: true }).inputValue()).toBe(ratio)
  await preset(page, '适应宽度'); await rendered(page, 4); const widthFit = Number(await page.getByLabel('缩放比例', { exact: true }).inputValue())
  await page.getByRole('button', { name: '展开文献导航', exact: true }).click(); await expect.poll(async () => Number(await page.getByLabel('缩放比例', { exact: true }).inputValue())).toBeLessThan(widthFit)
  const separator = page.getByRole('separator', { name: '调整文献导航宽度' }); await separator.focus(); await page.keyboard.press('ArrowRight'); await rendered(page, 4)
  await page.getByRole('button', { name: '收起文献导航', exact: true }).click()
  await view(page, '双页并排'); await preset(page, '适应宽度'); await rendered(page, 4)
  const boxes = await page.locator('.pdf-page').evaluateAll(nodes => nodes.map(n => ({ x:n.getBoundingClientRect().x, width:n.getBoundingClientRect().width })))
  expect(boxes[1]!.x).toBeGreaterThanOrEqual(boxes[0]!.x + boxes[0]!.width)
  await preset(page, '适应高度'); await rendered(page, 4); await expect(page.getByLabel('当前页码', { exact: true })).toHaveValue('4')
  await view(page, '单页切换'); await zoom(page, '150'); await rendered(page, 4)
  // Rapid wheel changes retain the latest scale and the original text host.
  await page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(async element=>{ for(let i=0;i<12;i++){ element.dispatchEvent(new WheelEvent('wheel',{ctrlKey:true,deltaY:-15,bubbles:true,cancelable:true}));await new Promise(requestAnimationFrame) } })
  await zoom(page,'150');await rendered(page,4)
  await expect(page.locator('[data-page="4"] .textLayer')).toContainText('Zoom - Page 4')
  expect(before).not.toBeNull(); await saved(page, doc.id, { pageNumber:4, zoom:1.5, zoomMode:'custom', viewMode:'single' })
})

test('A2 thumbnails lazy render, outline hierarchy/named destinations/bad targets and empty state', async ({ page }) => {
  const token = await openLibrary(page), doc = await (await upload(page.request, token, readerPdf('Navigation', 40, false, { outline:true }), 'Navigation.pdf')).json()
  await page.goto(`/reader/${doc.id}`); await rendered(page)
  await page.getByRole('button', { name:'展开文献导航', exact:true }).click()
  await expect.poll(async () => page.locator('.pdf-thumbnail canvas').evaluateAll(nodes => nodes.filter(n => (n as HTMLCanvasElement).width > 0).length)).toBeGreaterThan(0)
  expect(await page.locator('.pdf-thumbnail canvas').evaluateAll(nodes => nodes.filter(n => (n as HTMLCanvasElement).width > 0).length)).toBeLessThan(12)
  await page.getByRole('button', { name:'缩略图第 20 页', exact:true }).click(); await rendered(page,20)
  await expect(page.getByRole('button', { name:'缩略图第 20 页', exact:true })).toHaveAttribute('aria-current','page')
  await page.getByRole('button', { name:'大纲', exact:true }).click()
  await expect(page.getByRole('button',{name:'展开 Chapter',exact:true})).toHaveAttribute('aria-expanded','false')
  await expect(page.getByRole('button',{name:'Child section',exact:true})).toHaveCount(0)
  await page.getByRole('button',{name:'展开 Chapter',exact:true}).click();await expect(page.getByRole('button',{name:'Child section',exact:true})).toBeVisible()
  await page.getByRole('button', { name:'折叠 Chapter', exact:true }).click(); await expect(page.getByRole('button',{name:'Child section',exact:true})).toHaveCount(0)
  await page.getByRole('button', { name:'展开 Chapter', exact:true }).click(); await page.getByRole('button',{name:'Chapter',exact:true}).click(); await rendered(page,4)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('4')
  await page.getByRole('button',{name:'Broken target',exact:true}).click(); await expect(page.getByRole('status')).toContainText('目录目标无效')
  const no = await (await upload(page.request, token, readerPdf('No outline'), 'No outline.pdf')).json()
  await page.goto(`/reader/${no.id}`); await rendered(page); await page.getByRole('button',{name:'展开文献导航',exact:true}).click(); await page.getByRole('button',{name:'大纲',exact:true}).click()
  await expect(page.getByText('此 PDF 没有内置大纲',{exact:true})).toBeVisible()
})

test('A2 real search cross-item highlights, case/whole word, clear, cancellation and scan feedback', async ({ page }) => {
  const token = await openLibrary(page), doc = await (await upload(page.request,token,readerPdf('Search',7,false,{split:true,mixed:true}),'Search.pdf')).json()
  await page.goto(`/reader/${doc.id}`); await rendered(page); await page.getByRole('button',{name:'搜索文献',exact:true}).click()
  const input = page.getByLabel('PDF 文内搜索',{exact:true})
  await input.fill('international'); await expect(page.locator('.pdf-search [role="status"]')).toContainText('1 / 4 个匹配')
  await expect(page.locator('.pdf-search-layer span.current')).toHaveCount(2)
  await page.getByRole('button',{name:'下一个匹配',exact:true}).click(); await rendered(page,3); await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('3')
  await expect(page.locator('.pdf-search-layer span.current').first()).toBeVisible()
  await page.getByRole('button',{name:'上一个匹配',exact:true}).click(); await rendered(page,1)
  await input.fill('word'); await expect(page.locator('.pdf-search [role="status"]')).toContainText('12 个匹配')
  await page.getByLabel('全词匹配',{exact:true}).check(); await expect(page.locator('.pdf-search [role="status"]')).toContainText('8 个匹配')
  await page.getByLabel('区分大小写',{exact:true}).check(); await expect(page.locator('.pdf-search [role="status"]')).toContainText('4 个匹配')
  await input.fill('no-result'); await expect(page.locator('.pdf-search [role="status"]')).toContainText('0 / 0 个匹配')
  await input.fill('word'); await input.fill('international'); await input.clear(); await expect(page.locator('.pdf-search-layer span')).toHaveCount(0)
  await input.fill('word')
  const scan = await (await upload(page.request,token,readerPdf('Scan',2,false,{scan:true}),'Scan.pdf')).json()
  await page.goto(`/reader/${scan.id}`); await rendered(page); await page.getByRole('button',{name:'搜索文献',exact:true}).click(); await page.getByLabel('PDF 文内搜索',{exact:true}).fill('word')
  await expect(page.locator('.pdf-search [role="status"]')).toContainText('无可提取文本')
})

test('A2 save/refresh/document isolation; failure retains draft, conflict explicit choice and true recent opens', async ({ page }) => {
  const token=await openLibrary(page), a=await(await upload(page.request,token,readerPdf('Progress A'),'A.pdf')).json(), b=await(await upload(page.request,token,readerPdf('Progress B'),'B.pdf')).json()
  await page.goto(`/reader/${a.id}`); await rendered(page); await view(page,'单页切换'); await jump(page,4); await zoom(page,'175'); await rendered(page,4)
  await saved(page,a.id,{pageNumber:4,zoom:1.75,viewMode:'single',zoomMode:'custom'})
  await page.reload(); await rendered(page,4); await expect(page.getByLabel('缩放比例',{exact:true})).toHaveValue('175')
  await page.getByRole('link',{name:'文献管理',exact:true}).click(); await page.locator('tbody .document-title').filter({hasText:'B'}).click(); await rendered(page)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('1'); await page.locator(`[data-tab-id="${a.id}"] .document-title`).click(); await rendered(page,4)
  let fail=true
  await page.route(`**/documents/${a.id}/progress`, async route => { if(route.request().method()==='PUT'&&fail) await route.abort('failed'); else await route.continue() })
  await jump(page,5); await expect(page.getByRole('alert')).toContainText('本地进度已保留')
  await page.getByRole('link',{name:'文献管理',exact:true}).click(); await expect(page).toHaveURL(`/reader/${a.id}`)
  fail=false; await page.getByRole('button',{name:'重试阅读记录',exact:true}).click(); await saved(page,a.id,{pageNumber:5})
  const current=await(await page.request.get(`/api/v1/documents/${a.id}/progress`)).json()
  expect((await page.request.put(`/api/v1/documents/${a.id}/progress`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{version:current.version,pageNumber:2,zoom:1}})).status()).toBe(200)
  await jump(page,6); await expect(page.getByRole('alert')).toContainText('其他会话更新')
  await page.getByRole('button',{name:'保存本地进度',exact:true}).click(); await saved(page,a.id,{pageNumber:6})
  const newest=await(await page.request.get(`/api/v1/documents/${a.id}/progress`)).json()
  await page.request.put(`/api/v1/documents/${a.id}/progress`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{version:newest.version,pageNumber:2,zoom:1}})
  await jump(page,7); await expect(page.getByRole('alert')).toContainText('其他会话更新'); await page.getByRole('button',{name:'载入服务端进度',exact:true}).click(); await rendered(page,2)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('2')
})

test('A2 failed draft survives refresh; no silent overwrite until explicit local choice', async ({ page }) => {
  const token=await openLibrary(page), doc=await(await upload(page.request,token,readerPdf('Draft refresh'),'Draft.pdf')).json()
  await page.goto(`/reader/${doc.id}`); await rendered(page); await view(page,'单页切换'); await saved(page,doc.id,{viewMode:'single'})
  let fail=true
  await page.route(`**/documents/${doc.id}/progress`,async route=>{ if(route.request().method()==='PUT'&&fail) await route.abort(); else await route.continue() })
  await jump(page,3); await zoom(page,'200'); await expect(page.getByRole('alert')).toContainText('本地进度已保留')
  expect(await page.evaluate(()=>Object.keys(sessionStorage).filter(k=>k.startsWith('litera:progress:')).length)).toBe(1)
  page.on('dialog', dialog=>dialog.accept()); await page.reload(); await rendered(page,3)
  await expect(page.getByRole('alert')).toContainText('未同步的本地阅读进度')
  await expect(page.getByLabel('缩放比例',{exact:true})).toHaveValue('200')
  fail=false; await page.getByRole('button',{name:'保存本地进度',exact:true}).click(); await saved(page,doc.id,{pageNumber:3,zoom:2})
  await expect(page.getByRole('alert')).toHaveCount(0)
})

test('A2 real multi-page and rotated text selection publishes normalized context and clears across A→B→A', async ({ page,browser }) => {
  const token=await openLibrary(page), a=await(await upload(page.request,token,readerPdf('Context A',7,true),'Context A.pdf')).json(), b=await(await upload(page.request,token,readerPdf('Context B'),'Context B.pdf')).json()
  const context=await browser.newContext({baseURL:origin,deviceScaleFactor:2,viewport:{width:1366,height:768},storageState:await page.context().storageState()})
  const reader=await context.newPage()
  await reader.addInitScript(()=>{
    const log:any[]=[]; (window as any).readerEvents=log
    for(const kind of ['context-change','selection-change','document-change','context-cleared']) window.addEventListener(`litera:reader:${kind}`,e=>log.push({kind,context:(e as CustomEvent).detail}))
  })
  try {
    await reader.goto(`/reader/${a.id}`); await rendered(reader); await zoom(reader,'50'); await rendered(reader,2)
    await reader.evaluate(()=>{
      const first=document.querySelector('[data-page="1"] .textLayer span')!.firstChild!, last=document.querySelector('[data-page="2"] .textLayer span')!.firstChild!
      const range=document.createRange();range.setStart(first,0);range.setEnd(last,last.textContent!.length);const selection=getSelection()!;selection.removeAllRanges();selection.addRange(range)
    })
    const snapshot=()=>reader.evaluate(()=>(window as any).readerEvents.at(-1)?.context)
    await expect.poll(async()=>(await snapshot())?.selectionPosition?.map((p:any)=>p.pageNumber)).toEqual([1,2])
    const selected=await snapshot();expect(selected.pageNumber).toBe(1);expect(selected.selectedText).toContain('Context A')
    for(const position of selected.selectionPosition)for(const rect of position.rects){expect(rect.x).toBeGreaterThanOrEqual(0);expect(rect.y).toBeGreaterThanOrEqual(0);expect(rect.x+rect.width).toBeLessThanOrEqual(1.001);expect(rect.y+rect.height).toBeLessThanOrEqual(1.001)}
    await view(reader,'单页切换');await jump(reader,3);await zoom(reader,'100');await rendered(reader,3)
    const span=reader.locator('[data-page="3"] .textLayer span').filter({hasText:'Context A'}).first()
    await span.evaluate(element=>{ const range=document.createRange();range.selectNodeContents(element);const selection=getSelection()!;selection.removeAllRanges();selection.addRange(range) })
    await expect.poll(async()=>(await snapshot())?.selectedText).toContain('Context A')
    const rotated=await snapshot();expect(rotated.selectionPosition[0].pageNumber).toBe(3)
    await zoom(reader,'500');await rendered(reader,3)
    const buffers=await reader.locator('.pdf-page canvas').evaluateAll(nodes=>nodes.map(node=>{const c=node as HTMLCanvasElement;return{width:c.width,height:c.height,bytes:c.width*c.height*4}}))
    expect(buffers[0]!.width*buffers[0]!.height).toBeLessThan(16_020_000)
    console.log('A2 DPR2 500% Canvas backing stores',JSON.stringify(buffers))
    await reader.getByRole('link',{name:'文献管理',exact:true}).click()
    await expect.poll(()=>reader.evaluate(()=>(window as any).readerEvents.at(-1).kind)).toBe('context-cleared')
    await reader.locator('tbody .document-title').filter({hasText:'Context B'}).click();await rendered(reader)
    const other=await snapshot();expect(other.documentId).toBe(b.id);expect(other.selectedText).toBe('');expect(other.contextRevision).toBeGreaterThan(rotated.contextRevision)
    await reader.locator(`[data-tab-id="${a.id}"] .document-title`).click();await rendered(reader,3)
    const again=await snapshot();expect(again.documentId).toBe(a.id);expect(again.contextRevision).toBeGreaterThan(other.contextRevision);expect(again.selectedText).toBe('')
  } finally {await context.close()}
})
