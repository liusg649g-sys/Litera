import { test, expect } from '@playwright/test'
import type { Page, Locator } from '@playwright/test'
import { openLibrary, upload, origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'

async function rendered(page:Page,n=1){await expect(page.locator(`.pdf-page[data-page="${n}"]`)).toHaveAttribute('data-status','已渲染')}
async function saved(page:Page,id:string,n:number){await expect.poll(async()=> (await (await page.request.get(`/api/v1/documents/${id}/annotations`)).json()).items.length).toBe(n);await expect.poll(async()=> (await page.locator('.annotation-save-status').allTextContents()).join('')).not.toMatch(/正在保存|未保存/)}
async function annotations(page:Page,id:string){return (await(await page.request.get(`/api/v1/documents/${id}/annotations`)).json()).items as any[]}
async function selection(page:Page,from=1,to=from){
  await page.evaluate(async({from,to})=>{
    const first=document.querySelector(`.pdf-page[data-page="${from}"] .textLayer span`)!.firstChild!, spans=document.querySelectorAll(`.pdf-page[data-page="${to}"] .textLayer span`),last=spans[spans.length-1]!.firstChild!
    const selected=new Promise<void>(resolve=>{const listener=()=>{window.removeEventListener('litera:reader:selection-change',listener);resolve()};window.addEventListener('litera:reader:selection-change',listener);setTimeout(()=>{window.removeEventListener('litera:reader:selection-change',listener);resolve()},1500)})
    const range=document.createRange();range.setStart(first,0);range.setEnd(last,last.textContent!.length);window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range);await selected
  },{from,to})
}
async function tool(page:Page,name:string){await page.getByRole('button',{name,exact:true}).click()}
async function pointObject(page:Page,type:string,content:string,n=1){await tool(page,type);await page.locator(`.pdf-page[data-page="${n}"] .annotation-overlay`).click({position:{x:200,y:250}});await page.getByLabel('批注正文',{exact:true}).fill(content);await tool(page,'保存批注');await expect.poll(async()=>await page.getByLabel('批注正文',{exact:true}).count()===0 || await page.getByRole('alert').count()>0).toBe(true)}
async function zoom(page:Page,n:number){const input=page.getByLabel('缩放比例',{exact:true});await input.fill(String(n));await input.press('Enter')}
async function view(page:Page,name:string){await page.locator('.reader-view-select').click();await page.getByRole('option',{name,exact:true}).click()}

async function caret(span:Locator, offset:number) {
  return span.evaluate((el,offset)=> { const r=document.createRange();r.setStart(el.firstChild!,offset);r.collapse(true);const b=r.getBoundingClientRect();return {x:b.x,y:b.y+b.height/2} },offset)
}
async function dragText(page:Page, first:Locator,start:number,last:Locator,end:number,reverse=false) {
  await first.scrollIntoViewIfNeeded()
  const a=await caret(first,start),b=await caret(last,end)
  await page.mouse.move(reverse?b.x:a.x,reverse?b.y:a.y);await page.mouse.down()
  await page.mouse.move(reverse?a.x:b.x,reverse?a.y:b.y,{steps:8});await page.mouse.up()
}

test('B1 inline comments and on-page free text confirm cancel resize wrap retry and document guards',async({page})=>{
  test.setTimeout(90000)
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Inline editing',3),'Inline.pdf')).json()
  const other=await(await upload(page.request,token,readerPdf('Other inline',1),'Other-inline.pdf')).json()
  await page.goto(`/reader/${other.id}`);await rendered(page)
  await page.getByRole('link',{name:'文献管理',exact:true}).click();await page.locator('tbody tr').filter({hasText:'Inline'}).filter({hasNotText:'Other'}).locator('.document-title').click();await rendered(page);await tool(page,'批注');await zoom(page,100);await rendered(page)
  await pointObject(page,'注释','原注释');await saved(page,doc.id,1)
  const comment=(await annotations(page,doc.id))[0],commentCard=page.locator(`[data-list-annotation="${comment.id}"]`)
  await tool(page,'阅读');await page.locator(`[data-annotation="${comment.id}"]`).click()
  await expect(commentCard).toHaveClass(/selected/);await expect(page.locator('.annotation-inline-form')).toHaveCount(0)
  await commentCard.getByRole('button',{name:'编辑',exact:true}).click()
  const body=page.getByLabel('批注正文',{exact:true})
  await body.fill('尚未确认的卡片草稿');await expect(page.locator('dialog:modal')).toHaveCount(0)
  await page.screenshot({path:'test-results/reader-b1-inline-comment.png'})
  await tool(page,'关闭批注列表');await expect(body).toHaveValue('尚未确认的卡片草稿')
  await page.getByRole('link',{name:'文献管理',exact:true}).click();await expect(page).toHaveURL(new RegExp(`/reader/${doc.id}$`))
  await page.locator(`[data-tab-id="${other.id}"] .document-title`).click()
  await expect(page).toHaveURL(new RegExp(`/reader/${doc.id}$`));await expect(body).toHaveValue('尚未确认的卡片草稿')
  await tool(page,'取消');expect((await annotations(page,doc.id))[0].content).toBe('原注释')
  await commentCard.getByRole('button',{name:'编辑',exact:true}).click();await body.fill('卡片内保存正文')
  await page.getByLabel('批注透明度',{exact:true}).fill('0.6');await tool(page,'保存批注')
  await expect(page.locator('.annotation-inline-form')).toHaveCount(0)
  expect((await annotations(page,doc.id))[0]).toMatchObject({content:'卡片内保存正文',style:{opacity:.6}})
  await tool(page,'批注');await tool(page,'自由文本');await page.locator('.annotation-overlay').first().click({position:{x:180,y:300}})
  await expect(page.locator('.free-text-input')).toBeVisible();await body.fill('取消的新建文本');await tool(page,'取消');expect(await annotations(page,doc.id)).toHaveLength(1)
  await pointObject(page,'自由文本','A text box with enough words to demonstrate wrapping across several lines.\n第二行中文混合文本');await saved(page,doc.id,2)
  const free=(await annotations(page,doc.id)).find(a=>a.type==='freeText'),shape=page.locator(`[data-annotation="${free.id}"] polygon`)
  await shape.dblclick();await expect(page.locator('.free-text-input')).toBeVisible()
  const originalBox=await shape.boundingBox(),original=JSON.parse(JSON.stringify(free))
  await page.getByLabel('批注字号',{exact:true}).fill('24')
  await tool(page,'选择批注');await tool(page,'橡皮擦');await expect(page.locator('.annotation-resize')).toHaveCount(8)
  await expect(body).toHaveValue(original.content);await expect(page.getByRole('button',{name:'橡皮擦',exact:true})).toHaveAttribute('aria-pressed','false')
  expect((await shape.boundingBox())!.width).toBeCloseTo(originalBox!.width,1)
  for(const v of ['单页切换','双页并排','单页连续滚动']) { await view(page,v);await rendered(page);await expect(body).toHaveValue(original.content) }
  for(const z of [50,200,100]) { await zoom(page,z);await rendered(page);await expect(body).toHaveValue(original.content);await expect(page.getByLabel('批注字号',{exact:true})).toHaveValue('24') }
  const pendingBefore=(await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).annotationRevision
  async function handleDrag(handle:string,dx:number,dy:number,cancel=false) {
    const h=page.locator(`[data-annotation="${free.id}"] [data-handle="${handle}"]`);await h.scrollIntoViewIfNeeded()
    const b=(await h.boundingBox())!;await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+dx,b.y+b.height/2+dy,{steps:5})
    await expect(page.locator('.drag-preview')).toHaveCount(1)
    if(cancel) await page.keyboard.press('Escape')
    await page.mouse.up()
  }
  for(const h of ['nw','n','ne','e','se','s','sw','w']) { await handleDrag(h,4,4);await expect(page.getByLabel('批注字号',{exact:true})).toHaveValue('24') }
  const bar=page.locator('.free-text-move'),barBox=(await bar.boundingBox())!,oldX=(await shape.boundingBox())!.x
  await page.mouse.move(barBox.x+barBox.width/4,barBox.y+barBox.height/2);await page.mouse.down();await page.mouse.move(barBox.x+barBox.width/4+18,barBox.y+barBox.height/2+12,{steps:5})
  await expect(page.locator('.drag-preview')).toHaveCount(1);expect((await shape.boundingBox())!.x-oldX).toBeCloseTo(18,0);await page.mouse.up()
  await handleDrag('e',-80,0)
  expect(await page.locator('.free-text-input').evaluate(el=>el.scrollHeight>el.clientHeight)).toBe(true)
  await page.screenshot({path:'test-results/reader-b1-inline-free.png'})
  expect((await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).annotationRevision).toBe(pendingBefore)
  const beforeCancel=(await shape.boundingBox())!;await handleDrag('se',30,30,true);expect((await shape.boundingBox())!.width).toBeCloseTo(beforeCancel.width,1)
  await tool(page,'取消');expect(await annotations(page,doc.id)).toContainEqual(original)
  await shape.dblclick();await body.fill('页面内保存并恢复\nnew line');await page.getByLabel('批注字号',{exact:true}).fill('19');await handleDrag('se',35,30)
  let fail=true;await page.route(`**/documents/${doc.id}/annotations/${free.id}`,route=>route.request().method()==='PATCH'&&fail ? route.abort('failed') : route.continue())
  await tool(page,'保存批注');await expect(page.getByRole('alert')).toContainText('批注未保存');await expect(body).toHaveValue('页面内保存并恢复\nnew line')
  fail=false;await tool(page,'保存批注');await expect(page.locator('.free-text-input')).toHaveCount(0)
  let persisted=(await annotations(page,doc.id)).find(a=>a.id===free.id)
  expect(persisted).toMatchObject({content:'页面内保存并恢复\nnew line',style:{fontSize:19}});expect(persisted.geometry.rect.width).toBeGreaterThan(original.geometry.rect.width)
  await page.getByLabel('PDF 阅读区域',{exact:true}).focus();await page.keyboard.press('Control+z');await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id).content).toBe(original.content)
  await page.keyboard.press('Control+y');await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id).content).toBe(persisted.content)
  await shape.dblclick();await body.fill('取消失败的已提交修改');fail=true
  await tool(page,'保存批注');await expect(page.getByRole('alert')).toContainText('批注未保存')
  await tool(page,'取消');await expect(page.getByRole('button',{name:'取消',exact:true})).toBeEnabled();await expect(body).toHaveValue('取消失败的已提交修改')
  fail=false;await tool(page,'取消');await expect(page.locator('.free-text-input')).toHaveCount(0)
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id)).toMatchObject({content:persisted.content,geometry:persisted.geometry,style:persisted.style})
  persisted=(await annotations(page,doc.id)).find(a=>a.id===free.id)
  for(const z of [50,200,500,100]) {
    await zoom(page,z);await rendered(page);await expect(shape).toBeAttached()
    const box=(await shape.boundingBox())!,paper=(await page.locator('[data-page="1"]').boundingBox())!
    expect(box.width/paper.width).toBeCloseTo(persisted.geometry.rect.width,4)
    expect(box.height/paper.height).toBeCloseTo(persisted.geometry.rect.height,4)
  }
  for(const v of ['单页切换','双页并排','单页连续滚动']) {await view(page,v);await rendered(page);await expect(shape).toBeAttached()}
  await page.reload();await rendered(page);expect((await annotations(page,doc.id)).find(a=>a.id===free.id)).toEqual(persisted)
  await shape.dblclick();await body.fill('切文献前草稿');await page.getByRole('link',{name:'文献管理',exact:true}).click();await expect(body).toHaveValue('切文献前草稿');await tool(page,'取消')
  await page.goto(`/reader/${other.id}`);await rendered(page);await expect(page.locator(`[data-annotation="${free.id}"]`)).toHaveCount(0);expect(await annotations(page,other.id)).toHaveLength(0)
})

test('B1 precise native drags, split-item continuity, copy-through and transient save feedback',async({page},testInfo)=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Precision',3,true,{annotation:true}),'Precision.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page)
  const first=page.locator('[data-page="1"] .textLayer span').filter({hasText:'Precision '}).last()
  const word=page.locator('[data-page="1"] .textLayer span').filter({hasText:'Compact italic'}).first()
  await dragText(page,word,8,word,14)
  expect(await page.evaluate(()=>getSelection()!.toString())).toBe('italic')
  await dragText(page,first,2,first,7)
  expect(await page.evaluate(()=>getSelection()!.toString())).toBe('ecisi')
  await tool(page,'批注');await tool(page,'高亮');await saved(page,doc.id,1)
  let items=await annotations(page,doc.id)
  expect(items[0].selectedText).toBe('ecisi');expect(items[0].position[0].textRanges[0]).toMatchObject({start:2,end:7})
  await expect(page.locator('.annotation-selected')).toHaveCount(0)
  await expect(page.locator('.annotation-saved-toast')).toBeVisible()
  const toast=(await page.locator('.annotation-saved-toast').boundingBox())!,region=(await page.locator('.pdf-reading-region').boundingBox())!
  expect(Math.abs(toast.x+toast.width/2-region.x-region.width/2)).toBeLessThan(1)
  expect(toast.y-region.y).toBeCloseTo(12,0)
  await expect(page.locator('.annotation-saved-toast')).toHaveCount(0,{timeout:3000})
  await tool(page,'阅读');await dragText(page,first,2,first,7,true)
  expect(await page.evaluate(()=>getSelection()!.toString())).toBe('ecisi')
  await page.context().grantPermissions(['clipboard-read','clipboard-write']);await page.keyboard.press('Control+c')
  expect(await page.evaluate(()=>navigator.clipboard.readText())).toBe('ecisi')
  const last=page.locator('[data-page="1"] .textLayer span').filter({hasText:'items and spaces.'}).last()
  await tool(page,'批注')
  for(const name of ['高亮','下划线','波浪线','删除线']) {
    await dragText(page,first,3,last,8,name==='删除线');await tool(page,name)
  }
  await saved(page,doc.id,5);items=await annotations(page,doc.id)
  const full=items.filter(a=>a.selectedText!=='ecisi')
  expect(full).toHaveLength(4)
  expect(new Set(full.map(a=>a.type)).size).toBe(4)
  for(const item of full) {
    expect(item.position[0].rects).toHaveLength(1)
    expect(item.position[0].textRanges.length).toBeGreaterThan(1)
    expect(item.selectedText.startsWith('cision')).toBe(true)
    expect(item.position).toEqual(full[0].position)
  }
  await zoom(page,200);await rendered(page);await first.scrollIntoViewIfNeeded()
  for (const item of full) await page.locator('[data-page="1"]').screenshot({path:`test-results/reader-b1-visual-${item.type}.png`,style:`.annotation-hit:not([data-annotation="${item.id}"]) { visibility:hidden }`})
  await zoom(page,100);await rendered(page);await first.scrollIntoViewIfNeeded()
  const wave=page.locator(`[data-annotation="${full.find(a=>a.type==='squiggly').id}"] path`)
  await expect(wave).toHaveAttribute('d',/ Q /);await expect(wave).toHaveAttribute('stroke-linejoin','round')
  // A text click selects through the layer; Esc, blank click and reading clear it.
  await page.mouse.click((await caret(first,5)).x,(await caret(first,5)).y)
  await expect(page.locator('.annotation-selected').first()).toBeAttached();await page.keyboard.press('Escape')
  await expect(page.locator('.annotation-selected')).toHaveCount(0)
  for (const z of [50,200,500,100]) {
    await zoom(page,z);await rendered(page);await dragText(page,first,1,first,4,z===200)
    expect(await page.evaluate(()=>getSelection()!.toString())).toBe('rec')
  }
  for (const mode of ['单页切换','双页并排','单页连续滚动']) {
    await view(page,mode);await rendered(page);await dragText(page,first,1,first,4,true)
    expect(await page.evaluate(()=>getSelection()!.toString())).toBe('rec')
  }
  const italic=page.locator('[data-page="1"] .textLayer span').filter({hasText:'Compact italic'}).first()
  await dragText(page,first,3,italic,20,true);await tool(page,'下划线');await saved(page,doc.id,6)
  items=await annotations(page,doc.id)
  expect(items.find(a=>a.selectedText.includes('Compact italic')).position[0].rects).toHaveLength(2)
  await page.screenshot({path:'test-results/reader-b1-precision.png',fullPage:true})
  await testInfo.attach('split-text-items-and-selection',{body:JSON.stringify({items,spans:await page.locator('[data-page="1"] .textLayer span').evaluateAll(spans=>spans.map(el=>({text:el.textContent,item:(el as HTMLElement).dataset.textItem,rect:el.getBoundingClientRect().toJSON()})))},null,2),contentType:'application/json'})
  await page.reload();await rendered(page);expect(await annotations(page,doc.id)).toEqual(items)
})

test('B1 six real annotations create/edit/reload/delete/undo/redo and list navigation',async({page})=>{
  test.setTimeout(90000)
  const token=await openLibrary(page),bytes=readerPdf('B1 six',7,true,{split:true}),doc=await(await upload(page.request,token,bytes,'B1.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await tool(page,'批注')
  for(const name of ['高亮','下划线','波浪线','删除线']){await selection(page);await tool(page,name)}
  await pointObject(page,'注释','持久注释正文');await pointObject(page,'自由文本','自由文本\n第二行');await saved(page,doc.id,6)
  let items=await annotations(page,doc.id);expect(new Set(items.map(a=>a.type)).size).toBe(6)
  expect(items.find(a=>a.type==='highlight').position[0].rects.length).toBeGreaterThan(1)
  await tool(page,'批注列表');await expect(page.locator('.annotation-card')).toHaveCount(6)
  const commentForLocate=items.find(a=>a.type==='comment')
  await page.locator(`[data-list-annotation="${commentForLocate.id}"] .annotation-card-main`).click()
  await expect.poll(async()=> {
    const marker=(await page.locator(`[data-annotation="${commentForLocate.id}"]`).boundingBox())!, region=(await page.getByLabel('PDF 阅读区域',{exact:true}).boundingBox())!
    return Math.abs(marker.y-region.y-12)
  }).toBeLessThan(3)

  const controls=page.locator('.annotation-list-controls'), scroller=page.getByRole('region',{name:'批注条目',exact:true})
  const controlsBefore=(await controls.boundingBox())!, readingTop=await page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(el=>el.scrollTop)
  await scroller.evaluate(el=>{el.scrollTop=el.scrollHeight})
  await expect.poll(()=>scroller.evaluate(el=>el.scrollTop)).toBeGreaterThan(0)
  expect((await controls.boundingBox())!.y).toBeCloseTo(controlsBefore.y,1)
  expect(await page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(el=>el.scrollTop)).toBe(readingTop)
  await scroller.evaluate(el=>{el.scrollTop=0})
  await tool(page,'搜索文献');await expect(page.getByLabel('PDF 文内搜索',{exact:true})).toBeVisible();await tool(page,'批注列表')
  expect((await controls.boundingBox())!.y).toBeCloseTo(controlsBefore.y,1)
  for (const item of items) {
    await page.locator(`[data-list-annotation="${item.id}"]`).getByRole('button',{name:'编辑',exact:true}).click()
    const palette=page.getByRole('group',{name:'批注颜色选择',exact:true})
    await expect(palette.getByRole('button')).toHaveCount(4)
    await palette.getByRole('button',{name:'编辑批注颜色 #9B0000',exact:true}).click()
    await expect(palette.getByRole('button',{name:'编辑批注颜色 #9B0000',exact:true})).toHaveAttribute('aria-pressed','true')
    await expect(page.getByLabel('编辑批注颜色',{exact:true})).toHaveValue('#9b0000')
    await tool(page,'取消')
  }
  expect(await annotations(page,doc.id)).toEqual(items)
  const free=items.find(a=>a.type==='freeText'),card=page.locator(`[data-list-annotation="${free.id}"]`)
  await card.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('批注正文',{exact:true}).fill('修改后正文');await page.getByLabel('批注字号',{exact:true}).fill('22');await page.getByLabel('编辑批注颜色',{exact:true}).fill('#123456');await tool(page,'保存批注');await saved(page,doc.id,6)
  await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id)).toMatchObject({content:'修改后正文',color:'#123456',style:{fontSize:22}})
  await page.reload();await rendered(page);await tool(page,'批注列表');await expect(page.locator('.annotation-card')).toHaveCount(6)
  await expect(page.locator('.annotation-free-text')).toContainText('修改后正文')
  await page.getByLabel('批注排序',{exact:true}).selectOption('time');await expect(page.locator('.annotation-card').first()).toHaveAttribute('data-list-annotation',[...items].sort((a,b)=>b.createdAt.localeCompare(a.createdAt))[0].id)
  await page.getByLabel('批注排序',{exact:true}).selectOption('position')
  await page.getByLabel('批注类型筛选',{exact:true}).selectOption('freeText');await expect(page.locator('.annotation-card')).toHaveCount(1)
  await page.getByLabel('批注颜色筛选',{exact:true}).selectOption('#123456');await expect(page.locator('.annotation-card')).toHaveCount(1)
  const comment=items.find(a=>a.type==='comment')
  await page.locator(`[data-annotation="${comment.id}"]`).click();await expect(page.getByLabel('批注类型筛选',{exact:true})).toHaveValue('');await expect(page.getByLabel('批注颜色筛选',{exact:true})).toHaveValue('')
  await expect(page.locator(`[data-list-annotation="${comment.id}"]`)).toHaveClass(/selected/)
  await expect(page.locator('.annotation-editor')).not.toBeVisible()
  await page.locator(`[data-annotation="${free.id}"]`).click()
  await expect(page.locator(`[data-list-annotation="${free.id}"]`)).toHaveClass(/selected/)
  await expect(page.locator('.annotation-editor')).not.toBeVisible()
  await expect(page.getByRole('button',{name:'阅读',exact:true})).toHaveAttribute('aria-pressed','true')
  await expect(page.locator('.annotation-resize')).toHaveCount(0)
  const readShape=page.locator(`[data-annotation="${free.id}"] polygon`),readBox=(await readShape.boundingBox())!,beforeReadDrag=(await annotations(page,doc.id)).find(a=>a.id===free.id).geometry
  await page.mouse.move(readBox.x+10,readBox.y+10);await page.mouse.down();await page.mouse.move(readBox.x+40,readBox.y+25,{steps:5});await expect(page.locator('.drag-preview')).toHaveCount(0);await page.mouse.up()
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id).geometry).toEqual(beforeReadDrag)
  await expect(page.getByRole('button',{name:'阅读',exact:true})).toHaveAttribute('aria-pressed','true')
  await tool(page,'关闭批注列表');await readShape.click();await expect(page.locator(`[data-list-annotation="${free.id}"]`)).toBeVisible();await expect(page.locator('.annotation-resize')).toHaveCount(0)
  await tool(page,'关闭批注列表');await readShape.dblclick({delay:120});await expect(page.getByRole('button',{name:'批注',exact:true})).toHaveAttribute('aria-pressed','true');await expect(page.locator('.free-text-input')).toBeVisible();await expect(page.locator('.annotation-resize')).toHaveCount(8)
  await expect(page.locator('.free-text-move')).toHaveAttribute('stroke-opacity','0.35')
  expect(await page.locator('.free-text-input').evaluate(el=>parseFloat(getComputedStyle(el).paddingLeft)*el.getBoundingClientRect().width/el.clientWidth)).toBeCloseTo(3,0)
  await tool(page,'取消');await tool(page,'批注列表')
  await page.locator(`[data-list-annotation="${free.id}"]`).getByRole('button',{name:'编辑',exact:true}).click()
  await expect(page.locator('.free-text-input')).toBeVisible();await tool(page,'取消')
  await page.locator(`[data-list-annotation="${free.id}"]`).getByRole('button',{name:'删除',exact:true}).click();await saved(page,doc.id,5)
  await page.getByLabel('PDF 阅读区域',{exact:true}).focus();await page.keyboard.press('Control+z');await saved(page,doc.id,6)
  await page.keyboard.press('Control+y');await saved(page,doc.id,5)
  await tool(page,'批注');await tool(page,'撤销批注');await saved(page,doc.id,6);await tool(page,'重做批注');await saved(page,doc.id,5)
  expect(await(await page.request.get(`/api/v1/documents/${doc.id}/content?download=true`)).body()).toEqual(bytes)
  await page.screenshot({path:'test-results/reader-b1-six.png',fullPage:true})
})

test('B1 cross-page/line and rotated CropBox coordinates survive 50–500%, three views and refresh',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('B1 geometry',7,false,{split:true}),'Geometry.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await tool(page,'批注')
  await zoom(page,50);await rendered(page);await rendered(page,2);await selection(page,1,2);await tool(page,'高亮');await saved(page,doc.id,1)
  let items=await annotations(page,doc.id);expect(items[0].position.map((p:any)=>p.pageNumber)).toEqual([1,2])
  const input=page.getByLabel('当前页码',{exact:true});await input.fill('3');await input.press('Enter');await rendered(page,3);await selection(page,3);await tool(page,'下划线');await saved(page,doc.id,2)
  items=await annotations(page,doc.id);const rotated=items.find(a=>a.type==='underline')
  const errors:{zoom:number;cssPixels:number}[]=[]
  for(const z of [50,100,200,500]){
    await zoom(page,z);await rendered(page,3)
    const error=await page.locator(`[data-page="3"] [data-annotation="${rotated.id}"] polygon`).first().evaluate(poly=>{
      const range=document.createRange();range.selectNodeContents(document.querySelector('[data-page="3"] .textLayer span')!.firstChild!)
      const p=poly.getBoundingClientRect(), text=range.getBoundingClientRect()
      return { error:Math.max(Math.abs(p.x-text.x),Math.abs(p.y-text.y),Math.abs(p.width-text.width),Math.abs(p.height-text.height)), p:p.toJSON(), text:text.toJSON() }
    // DOM Range rounds font line boxes at small CSS sizes; compare in PDF points.
    });expect(error.error,JSON.stringify({z,...error,position:rotated.position})).toBeLessThan(Math.max(1.5,1.2*z/100))
    errors.push({zoom:z,cssPixels:error.error})
  }
  console.log('B1 rotated CropBox DOM Range difference',JSON.stringify(errors))
  await zoom(page,100)
  for(const mode of ['单页切换','双页并排','单页连续滚动']){await view(page,mode);await rendered(page,3);await expect(page.locator(`[data-page="3"] [data-annotation="${rotated.id}"]`).first()).toBeAttached()}
  await page.reload();await rendered(page,3);expect(await annotations(page,doc.id)).toEqual(items)
  await tool(page,'批注列表');await page.locator(`[data-list-annotation="${items[0].id}"] .annotation-card-main`).click();await rendered(page,1);await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('1')
  await page.locator(`[data-page="1"] [data-annotation="${items[0].id}"]`).first().click({force:true});await expect(page.locator(`[data-list-annotation="${items[0].id}"]`)).toHaveClass(/selected/)
})

test('B1 point comment/free text move/resize/edit keyboard focus and scan has no fabricated text',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('B1 scan',1,false,{scan:true}),'Scan.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await tool(page,'批注');await tool(page,'高亮')
  await page.locator('.pdf-page').click({position:{x:180,y:180}});expect(await annotations(page,doc.id)).toEqual([])
  await pointObject(page,'注释','扫描页注释');await pointObject(page,'自由文本','扫描页文本');await saved(page,doc.id,2)
  const items=await annotations(page,doc.id),free=items.find(a=>a.type==='freeText')
  const shape=page.locator(`[data-annotation="${free.id}"] polygon`);await shape.click();const box=(await shape.boundingBox())!
  await page.mouse.move(box.x+10,box.y+10);await page.mouse.down();await page.mouse.move(box.x+45,box.y+35,{steps:5});
  await expect(page.locator('.drag-preview')).toHaveCount(1)
  expect((await shape.boundingBox())!.x-box.x).toBeCloseTo(35,0)
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id).geometry).toEqual(free.geometry)
  await page.mouse.up()
  await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id).geometry.rect.x).not.toBe(free.geometry.rect.x)
  await page.keyboard.press('Control+z');await saved(page,doc.id,2)
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id).geometry).toEqual(free.geometry)
  await page.keyboard.press('Control+y');await saved(page,doc.id,2)
  await tool(page,'批注列表');await page.locator(`[data-list-annotation="${free.id}"] .annotation-card-main`).click()
  const moved=(await annotations(page,doc.id)).find(a=>a.id===free.id),resize=page.locator(`[data-annotation="${free.id}"] .annotation-resize[data-handle="se"]`),handle=(await resize.boundingBox())!
  await page.mouse.move(handle.x+5,handle.y+5);await page.mouse.down();await page.mouse.move(handle.x+35,handle.y+25,{steps:4});await page.mouse.up()
  await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id).geometry.rect.width).toBeGreaterThan(moved.geometry.rect.width)
  const comment=items.find(a=>a.type==='comment');await page.locator(`[data-list-annotation="${comment.id}"] .annotation-card-main`).click()
  const marker=(await page.locator(`[data-annotation="${comment.id}"]`).boundingBox())!
  await page.mouse.move(marker.x+marker.width/2,marker.y+marker.height/2);await page.mouse.down();await page.mouse.move(marker.x+marker.width/2+25,marker.y+marker.height/2+20,{steps:4});
  await expect(page.locator('.drag-preview')).toHaveCount(1)
  const beforeCancel=(await annotations(page,doc.id)).find(a=>a.id===comment.id).geometry
  await page.keyboard.press('Escape');await page.mouse.up()
  await expect(page.locator('.drag-preview')).toHaveCount(0)
  await expect(page.locator('.annotation-editor')).not.toBeVisible()
  expect((await annotations(page,doc.id)).find(a=>a.id===comment.id).geometry).toEqual(beforeCancel)
  await page.locator(`[data-list-annotation="${comment.id}"] .annotation-card-main`).click()
  const marker2=(await page.locator(`[data-annotation="${comment.id}"]`).boundingBox())!
  await page.mouse.move(marker2.x+marker2.width/2,marker2.y+marker2.height/2);await page.mouse.down();await page.mouse.move(marker2.x+marker2.width/2+25,marker2.y+marker2.height/2+20,{steps:4});await page.mouse.up()
  await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===comment.id).geometry.x).not.toBe(comment.geometry.x)
  await page.locator(`[data-annotation="${comment.id}"]`).click();await page.locator(`[data-list-annotation="${comment.id}"]`).getByRole('button',{name:'编辑',exact:true}).click();await expect(page.getByLabel('批注正文',{exact:true})).toHaveValue('扫描页注释');await tool(page,'取消')
  await page.locator(`[data-list-annotation="${free.id}"]`).getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('批注正文',{exact:true}).fill('输入框自己的撤销');const revision=(await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).annotationRevision
  await page.getByLabel('批注正文',{exact:true}).press('Control+z');expect((await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).annotationRevision).toBe(revision);await tool(page,'取消')
  await tool(page,'橡皮擦');await shape.click();await saved(page,doc.id,1);await tool(page,'撤销批注');await saved(page,doc.id,2)
  await tool(page,'选择批注')
  await shape.click();const beforeFailure=(await annotations(page,doc.id)).find(a=>a.id===free.id), b=(await shape.boundingBox())!
  let failMove=true
  await page.route(`**/documents/${doc.id}/annotations/${free.id}`,async route=>{if(failMove && route.request().method()==='PATCH')await route.abort('failed');else await route.continue()})
  await page.mouse.move(b.x+10,b.y+10);await page.mouse.down();await page.mouse.move(b.x+35,b.y+25,{steps:4});await page.mouse.up()
  await expect(page.getByRole('alert')).toContainText('批注未保存')
  await expect(page.locator('.annotation-saved-toast')).toHaveCount(0)
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id).geometry).toEqual(beforeFailure.geometry)
  expect((await shape.boundingBox())!.x-b.x).toBeCloseTo(25,0)
  failMove=false;await tool(page,'重试保存批注');await saved(page,doc.id,2)
  await expect.poll(async()=> (await annotations(page,doc.id)).find(a=>a.id===free.id).geometry.rect.x).not.toBe(beforeFailure.geometry.rect.x)
  await tool(page,'撤销批注');await saved(page,doc.id,2)
  expect((await annotations(page,doc.id)).find(a=>a.id===free.id).geometry).toEqual(beforeFailure.geometry)

})

test('B1 lost response receipt retry, failed queue leave protection, refresh draft and real 409 conflict',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('B1 recovery'),'Recovery.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await tool(page,'批注')
  let lose=true
  await page.route(`**/documents/${doc.id}/annotations`,async route=>{if(route.request().method()==='POST'&&lose){lose=false;await route.fetch();await route.abort('failed')}else await route.continue()})
  await pointObject(page,'注释','结果未知但服务端已提交');await expect(page.getByRole('alert')).toContainText('批注未保存');expect(await annotations(page,doc.id)).toHaveLength(1)
  await tool(page,'重试保存批注');await saved(page,doc.id,1);await page.unroute(`**/documents/${doc.id}/annotations`)
  let fail=true
  await page.route(`**/documents/${doc.id}/annotations`,async route=>{if(route.request().method()==='POST'&&fail)await route.abort('failed');else await route.continue()})
  await pointObject(page,'自由文本','失败草稿保留');await expect(page.getByRole('alert')).toContainText('批注未保存')
  await expect(page.locator('.annotation-save-status')).toHaveCount(0,{timeout:4500});await expect(page.getByRole('alert')).toContainText('批注未保存')
  await page.getByRole('link',{name:'文献管理',exact:true}).click();await expect(page).toHaveURL(new RegExp(`/reader/${doc.id}$`))
  await tool(page,'保留批注草稿并返回文献库');await expect(page).toHaveURL('/library');await page.goto(`/reader/${doc.id}`);await rendered(page);await expect(page.getByRole('alert')).toContainText('发现未完成的批注草稿')
  page.on('dialog',dialog=>dialog.accept());await page.reload();await rendered(page);await expect(page.getByRole('alert')).toContainText('发现未完成的批注草稿')
  fail=false;await tool(page,'重试保存批注');await saved(page,doc.id,2);await page.unroute(`**/documents/${doc.id}/annotations`)
  const snapshot=await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json(),other={...snapshot.items[0],id:crypto.randomUUID(),content:'另一会话写入'}
  for(const k of ['documentId','version','createdAt','updatedAt'])delete other[k]
  expect((await page.request.post(`/api/v1/documents/${doc.id}/annotations`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{commandId:crypto.randomUUID(),baseRevision:snapshot.annotationRevision,annotation:other}})).status()).toBe(201)
  await tool(page,'批注');await pointObject(page,'注释','本地冲突草稿');await expect(page.getByRole('alert')).toContainText('并发冲突');expect(await annotations(page,doc.id)).toHaveLength(3)
  const download=page.waitForEvent('download');await tool(page,'导出批注草稿');expect((await download).suggestedFilename()).toContain('litera-annotations')
  await tool(page,'载入服务端批注并保留草稿备份');await expect(page.getByRole('alert')).toHaveCount(0);await expect(page.locator('.annotation-save-status')).toContainText('草稿备份已保留')
  await expect(page.getByRole('button',{name:'导出保留草稿',exact:true})).toBeVisible()
  await expect(page.locator('.annotation-save-status')).toHaveCount(0,{timeout:4500})
  await tool(page,'批注列表');await expect(page.getByRole('button',{name:'导出草稿备份',exact:true})).toBeVisible()
  const backupDownload=page.waitForEvent('download');await tool(page,'导出草稿备份');expect((await backupDownload).suggestedFilename()).toContain('litera-annotations')
})

test('B1 narrow comment card edits inline without modal shading and keeps drafts until save/cancel',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('B1 narrow',1),'Narrow.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await tool(page,'批注');await pointObject(page,'注释','窄屏注释');await saved(page,doc.id,1)
  await page.setViewportSize({width:390,height:844})
  await expect(page.getByRole('dialog',{name:'批注列表',exact:true})).toBeVisible();await page.getByRole('button',{name:'编辑',exact:true}).click()
  await expect(page.locator('.annotation-inline-form')).toBeVisible();expect(await page.getByRole('dialog',{name:'批注列表',exact:true}).evaluate(el=>el.matches(':modal'))).toBe(false);await page.getByLabel('批注正文',{exact:true}).fill('窄屏真实保存')
  await page.screenshot({path:'test-results/reader-b1-editor-narrow.png',fullPage:true})
  await page.keyboard.press('Escape');await expect(page.locator('.annotation-inline-form')).toHaveCount(0);expect((await annotations(page,doc.id))[0].content).toBe('窄屏注释')
  await page.getByRole('button',{name:'编辑',exact:true}).click();await page.getByLabel('批注正文',{exact:true}).fill('窄屏真实保存')
  await page.getByRole('button',{name:'编辑批注颜色 #47A58E',exact:true}).click()
  expect(await page.locator('.annotation-inline-form').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true)
  await tool(page,'保存批注')
  await expect.poll(async()=> (await annotations(page,doc.id))[0].content).toBe('窄屏真实保存')
  expect((await annotations(page,doc.id))[0].color).toBe('#47A58E')
  await page.screenshot({path:'test-results/reader-b1-narrow.png',fullPage:true})
})


test('B1 superscript citations share one body line for all four marks and legacy split geometry',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Raised references',3,false,{scripts:true}),'Raised.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page);await tool(page,'批注')
  const first=page.locator('[data-page="1"] .textLayer span').filter({hasText:'Body network'}).first()
  const last=page.locator('[data-page="1"] .textLayer span').filter({hasText:'continuation text.'}).first()
  const end=await last.evaluate(el=>el.textContent!.length-1)
  for(const name of ['高亮','下划线','波浪线','删除线']) {await dragText(page,first,1,last,end);await tool(page,name)}
  await saved(page,doc.id,4)
  const items=await annotations(page,doc.id)
  for(const item of items) {
    expect(item.position[0].rects.length).toBeGreaterThan(1)
    expect(item.selectedText).toContain('[6]')
    expect(item.selectedText).not.toContain('Previous')
    expect(item.selectedText).not.toContain('Next')
  }
  async function aligned() {
    const shapes=[]
    for(const item of items) {
      const mark=page.locator(`[data-page="1"] [data-annotation="${item.id}"]`)
      await expect(mark).toHaveCount(1)
      shapes.push(await mark.locator('polygon').getAttribute('points'))
      if(['underline','strikeout'].includes(item.type)) expect(await mark.locator('line').getAttribute('y1')).toBe(await mark.locator('line').getAttribute('y2'))
    }
    expect(new Set(shapes).size).toBe(1)
  }
  for(const z of [50,100,200,500]) {await zoom(page,z);await rendered(page);await aligned()}
  await zoom(page,100)
  for(const mode of ['单页切换','双页并排','单页连续滚动']) {await view(page,mode);await rendered(page);await aligned()}
  await first.scrollIntoViewIfNeeded()
  for(const item of items) await page.locator('[data-page="1"]').screenshot({path:`test-results/reader-b1-raised-${item.type}.png`,style:`.annotation-hit:not([data-annotation="${item.id}"]) { visibility:hidden }`})
  await page.reload();await rendered(page);await aligned()
  expect(await annotations(page,doc.id)).toEqual(items)
})


async function quickPanel(page:Page){
  await tool(page,'批注')
  const span=page.locator('[data-page="1"] .textLayer span').first()
  const length=(await span.textContent())!.length,end=Math.min(length,14)
  await dragText(page,span,1,span,end)
  const text=await page.evaluate(()=>window.getSelection()?.toString())
  const at=await caret(span,Math.min(5,end-1))
  await page.mouse.click(at.x,at.y,{button:'right'})
  const panel=page.getByRole('toolbar',{name:'选区批注快捷面板',exact:true})
  await expect(panel).toBeVisible()
  await expect(panel).toHaveCSS('opacity','1')
  return {panel,text,span}
}

test('B1 selection quick panel creates exactly five anchored annotation types',async({page},info)=>{
  test.setTimeout(90000)
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Quick selection toolbar',3))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page)
  const kinds=['highlight','underline','squiggly','strikeout','comment']
  for(const [i,label] of ['高亮','下划线','波浪线','删除线','注释'].entries()){
    const {panel,text}=await quickPanel(page)
    await expect(panel.getByRole('group',{name:'快捷批注工具',exact:true}).getByRole('button')).toHaveCount(5)
    await expect(panel.getByRole('button',{name:'自由文本',exact:true})).toHaveCount(0)
    await expect(panel.getByRole('button',{name:'手绘',exact:true})).toHaveCount(0)
    const colors=['#9B0000','#47A58E','#6395CF','#F5D547','#123456'],color=colors[i]!
    if(i<4){await panel.getByRole('button',{name:'快捷批注颜色 '+color,exact:true}).click();await expect(panel.getByRole('button',{name:'快捷批注颜色 '+color,exact:true})).toHaveAttribute('aria-pressed','true')}
    else {
      const custom=panel.getByLabel('快捷批注自定义颜色',{exact:true})
      await custom.dispatchEvent('pointerdown',{pointerType:'mouse'})
      await page.evaluate(()=>window.dispatchEvent(new Event('blur')))
      await expect(panel).toBeVisible()
      await custom.fill(color)
      await custom.dispatchEvent('pointerdown',{pointerType:'mouse'});await custom.dispatchEvent('cancel')
    }
    await expect(panel).toBeVisible();expect(await page.evaluate(()=>window.getSelection()?.toString())).toBe(text)
    expect((await annotations(page,doc.id)).length).toBe(i)
    if(i===0)await page.screenshot({path:info.outputPath('selection-quick-toolbar.png')})
    await panel.getByRole('button',{name:label,exact:true}).click()
    await expect(panel).toHaveCount(0)
    if(label==='注释'){
      await expect(page.getByLabel('批注正文',{exact:true})).toBeVisible()
      await page.getByLabel('批注正文',{exact:true}).fill('来自选区右键的注释')
      await tool(page,'保存批注')
    }
    await saved(page,doc.id,i+1)
    const item=(await annotations(page,doc.id)).find(a=>a.type===kinds[i])
    expect(item.selectedText.trim()).toBe(text!.trim());expect(item.geometry.kind).toBe('text');expect(item.color.toUpperCase()).toBe(color)
    expect(item.position[0].textRanges[0]).toMatchObject({start:1,end:14})
  }
  await tool(page,'撤销批注');await saved(page,doc.id,4);await tool(page,'重做批注');await saved(page,doc.id,5)
  await page.reload();await rendered(page)
  expect((await annotations(page,doc.id)).map(a=>a.type).sort()).toEqual([...kinds].sort())
})

test('B1 selection quick panel fades by distance and clears on escape scroll selection and document changes',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Quick fade toolbar',3))).json()
  const other=await(await upload(page.request,token,readerPdf('Other quick toolbar',1))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page)
  let {panel,text}=await quickPanel(page)
  const b=(await panel.boundingBox())!
  const selected=await page.evaluate(()=>{const r=window.getSelection()!.getRangeAt(0).getBoundingClientRect();return {top:r.top,bottom:r.bottom}})
  expect(Math.min(Math.abs(b.y+b.height-selected.top),Math.abs(b.y-selected.bottom))).toBeLessThanOrEqual(12)
  await page.mouse.move(b.x+10,b.y+b.height/2)
  await expect(panel).toHaveCSS('opacity','1')
  await page.mouse.move(b.x-25,b.y+b.height/2)
  await expect.poll(async()=> Number(await panel.evaluate(el=>getComputedStyle(el).opacity))).toBeCloseTo(.5,1)
  await page.mouse.move(b.x+10,b.y+b.height/2);await expect(panel).toHaveCSS('opacity','1')
  await page.mouse.move(b.x-51,b.y+b.height/2);await expect(panel).toHaveCount(0)
  expect(await page.evaluate(()=>window.getSelection()?.toString())).toBe(text)
  ;({panel}=await quickPanel(page));await tool(page,'阅读');await expect(panel).toHaveCount(0)
  ;({panel}=await quickPanel(page));await page.keyboard.press('Escape');await expect(panel).toHaveCount(0)
  ;({panel}=await quickPanel(page));await page.evaluate(()=>window.getSelection()?.removeAllRanges());await expect(panel).toHaveCount(0)
  ;({panel}=await quickPanel(page));await page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(el=>el.scrollTop+=100);await expect(panel).toHaveCount(0)
  ;({panel}=await quickPanel(page));await page.goto(`/reader/${other.id}`);await rendered(page);await expect(panel).toHaveCount(0)
  expect(await annotations(page,doc.id)).toHaveLength(0);expect(await annotations(page,other.id)).toHaveLength(0)
})


test('B1 selection quick panel supports fullscreen keyboard and preserves ordinary context menus',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Keyboard quick toolbar',2))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page)
  await page.evaluate(()=>document.addEventListener('contextmenu',e=>{(window as any).__ordinaryMenuPrevented=e.defaultPrevented}))
  await page.locator('[data-page="1"]').click({position:{x:50,y:300},button:'right'})
  await expect(page.getByRole('toolbar',{name:'选区批注快捷面板',exact:true})).toHaveCount(0)
  expect(await page.evaluate(()=>(window as any).__ordinaryMenuPrevented)).toBe(false)
  await page.keyboard.press('Escape')
  const readingSpan=page.locator('[data-page="1"] .textLayer span').first()
  await dragText(page,readingSpan,1,readingSpan,14)
  const readingPoint=await caret(readingSpan,5)
  await page.mouse.click(readingPoint.x,readingPoint.y,{button:'right'})
  await expect(page.getByRole('toolbar',{name:'选区批注快捷面板',exact:true})).toHaveCount(0)
  expect(await page.evaluate(()=>(window as any).__ordinaryMenuPrevented)).toBe(false)
  await page.keyboard.press('Escape')
  await tool(page,'全屏阅读');await expect(page.locator('.reader-brandbar-slot')).toHaveCSS('height','0px')
  let {panel}=await quickPanel(page)
  expect(await panel.evaluate(el=>document.fullscreenElement?.contains(el))).toBe(true)
  await panel.getByRole('button',{name:'下划线',exact:true}).click();await saved(page,doc.id,1)
  await page.evaluate(()=>document.exitFullscreen());await expect(page.locator('.reader-brandbar-slot')).toHaveCSS('height','48px')
  const span=page.locator('[data-page="1"] .textLayer span').first()
  await dragText(page,span,1,span,14)
  await page.keyboard.press('Shift+F10')
  panel=page.getByRole('toolbar',{name:'选区批注快捷面板',exact:true})
  await expect(panel).toBeVisible();await expect(panel.getByRole('button',{name:'高亮',exact:true})).toBeFocused()
  await page.keyboard.press('Enter');await saved(page,doc.id,2)
})


test('B1 selection quick panel anchors to the clicked line of a multi-page selection and fits narrow screens',async({page})=>{
  const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('Multi page quick toolbar',3))).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,100);await rendered(page)
  await tool(page,'批注')
  const second=page.locator('[data-page="2"] .textLayer span').first()
  await page.locator('[data-page="2"]').scrollIntoViewIfNeeded();await rendered(page,2)
  await second.scrollIntoViewIfNeeded()
  await selection(page,1,2)
  const at=await caret(second,4)
  await page.mouse.click(at.x,at.y,{button:'right'})
  const panel=page.getByRole('toolbar',{name:'选区批注快捷面板',exact:true})
  await expect(panel).toBeVisible();await expect(panel).toHaveCSS('opacity','1')
  const r=(await panel.boundingBox())!
  expect(Math.max(r.y-at.y,at.y-r.y-r.height,0)).toBeLessThan(50)
  await panel.getByRole('button',{name:'高亮',exact:true}).click();await saved(page,doc.id,1)
  expect((await annotations(page,doc.id))[0].position.map((p:any)=>p.pageNumber)).toEqual([1,2])
  await page.setViewportSize({width:390,height:844});await zoom(page,50);await rendered(page)
  const narrow=await quickPanel(page),b=(await narrow.panel.boundingBox())!
  expect(b.x).toBeGreaterThanOrEqual(0);expect(b.x+b.width).toBeLessThanOrEqual(390)
  await narrow.panel.getByRole('button',{name:'下划线',exact:true}).click();await saved(page,doc.id,2)
})
