import { test,expect,type Page } from '@playwright/test'
import { openLibrary,upload,origin } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
const button=(p:Page,name:string)=>p.getByRole('button',{name,exact:true})
async function rendered(p:Page,n=1){await expect(p.locator(`.pdf-page[data-page="${n}"]`)).toHaveAttribute('data-status','已渲染')}
async function items(p:Page,id:string){return (await(await p.request.get(`/api/v1/documents/${id}/annotations`)).json()).items as any[]}
async function setup(p:Page){p.on('pageerror',e=>console.log('B2 PAGE ERROR',e.message));const token=await openLibrary(p),bytes=readerPdf('B2 '+Date.now(),7,true),doc=await(await upload(p.request,token,bytes)).json();await p.goto(`/reader/${doc.id}`);await rendered(p);const zoom=p.getByLabel('缩放比例',{exact:true});await zoom.fill('100');await zoom.press('Enter');await rendered(p);return {doc,token,bytes}}
async function group(p:Page,name:string){await button(p,name).click()}
async function draw(p:Page,type:string,n=1){await button(p,type).click();const overlay=p.locator(`[data-page="${n}"] .drawing-overlay`);await overlay.scrollIntoViewIfNeeded();const r=(await overlay.boundingBox())!;await p.mouse.move(r.x+100,r.y+160);await p.mouse.down();await p.mouse.move(r.x+240,r.y+245,{steps:12});await expect(p.locator('[data-drawing="preview"], [data-drawing^="ink-preview"]')).toHaveCount(1);await p.mouse.up()}
async function save(p:Page,id:string,n:number){await button(p,'保存批注').click();await expect(p.locator('.drawing-controls')).toHaveCount(0);await expect.poll(async()=> (await items(p,id)).length).toBe(n)}
async function zoom(p:Page,n:number,pageNumber=1){const z=p.getByLabel('缩放比例',{exact:true});await z.fill(String(n));await z.press('Enter');await rendered(p,pageNumber)}
async function imageFile(p:Page,fmt='image/png'){return Buffer.from(await p.evaluate(fmt=>{const c=document.createElement('canvas');c.width=120;c.height=60;const ctx=c.getContext('2d')!;ctx.fillStyle='#47A58E';ctx.fillRect(0,0,120,60);return c.toDataURL(fmt).split(',')[1]!},fmt),'base64')}
async function place(p:Page,type:string){await button(p,type).click();if(type==='图片')await p.getByLabel('选择本地图片',{exact:true}).setInputFiles({name:'sample.png',mimeType:'image/png',buffer:await imageFile(p)});await expect(button(p,type)).toHaveAttribute('aria-pressed','true');const r=(await p.locator('[data-page="1"] .drawing-overlay').boundingBox())!;await p.mouse.move(r.x+310,r.y+300);await expect(p.locator('[data-drawing="preview"]')).toHaveCount(1);await p.mouse.click(r.x+310,r.y+300)}

async function deletionObjects(page:Page) {
  const context=await setup(page),{doc,token}=context,headers={Origin:origin,'X-CSRF-Token':token},base=`/api/v1/documents/${doc.id}`
  const asset=await(await page.request.post(base+'/reader-assets',{headers,multipart:{file:{name:'delete.png',mimeType:'image/png',buffer:await imageFile(page)}}})).json()
  const objects:any[]=[]
  for(const [i,type] of ['ink','rectangle','circle','ellipse','signature','watermark','image'].entries()) {
    const x=.08+(i%3)*.3,y=.14+Math.floor(i/3)*.19,width=.18,height=type==='circle'?width*612/792:['image','signature'].includes(type)?width*612/792/2:.09
    const annotation={id:crypto.randomUUID(),type,schemaVersion:1,pageNumber:1,geometry:type==='ink'?{kind:'points',pageNumber:1,points:[{x,y},{x:x+width/2,y:y+.04},{x:x+width,y:y+.06}]}:{kind:'box',pageNumber:1,rect:{x,y,width,height},rotation:0},position:null,style:{opacity:1,lineWidth:2,fontSize:24},assetId:['image','signature'].includes(type)?asset.assetId:null,selectedText:null,content:type==='watermark'?'DELETE':null,color:'#9B0000',zIndex:0}
    const response=await page.request.post(base+'/annotations',{headers,data:{commandId:crypto.randomUUID(),baseRevision:i,annotation}})
    expect(response.status(),type+': '+await response.text()).toBe(201);objects.push((await response.json()).annotation)
  }
  await page.reload();await rendered(page);await zoom(page,100)
  return {...context,objects}
}
async function clickPaint(page:Page,a:any) {
  const selector=a.type==='ink'?'path':a.type==='rectangle'?'rect':['circle','ellipse'].includes(a.type)?'ellipse':a.type==='watermark'?'text':'image'
  const paint=page.locator(`[data-drawing="${a.id}"] ${selector}`).first();await paint.scrollIntoViewIfNeeded()
  const point=await paint.evaluate(el=>{
    const svg=el as SVGGraphicsElement,m=svg.getScreenCTM()!
    if(el.tagName.toLowerCase()==='path'){const path=el as SVGPathElement,p=path.getPointAtLength(path.getTotalLength()/2);const q=new DOMPoint(p.x,p.y).matrixTransform(m);return {x:q.x,y:q.y}}
    const r=svg.getBBox(),q=new DOMPoint(r.x+r.width/2,r.y+(['text','image'].includes(el.tagName.toLowerCase())?r.height/2:0)).matrixTransform(m);return {x:q.x,y:q.y}
  })
  await page.mouse.click(point.x,point.y)
}

test('B2 eraser deletes all seven types across tool groups with persisted undo redo and reload',async({page})=>{
  test.setTimeout(120000)
  const {doc,objects,bytes}=await deletionObjects(page)
  for(const [i,a] of objects.entries()) {
    await group(page,['插入','批注','形状'][i%3]!);await button(page,'橡皮擦').click()
    const shape=page.locator(`[data-drawing="${a.id}"]`)
    await expect(page.locator('.drawing-overlay').first()).toHaveClass(/erasing/)
    await expect(shape).toHaveCSS('pointer-events','visiblepainted')
    await expect(shape.locator('[data-handle]')).toHaveCount(0)
    await clickPaint(page,a)
    await expect.poll(async()=> (await items(page,doc.id)).some(item=>item.id===a.id)).toBe(false)
    await expect(shape).toHaveCount(0)
    await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
    expect((await items(page,doc.id)).find(item=>item.id===a.id)).toMatchObject({type:a.type,geometry:a.geometry,assetId:a.assetId})
    await button(page,'重做批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(6)
    await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
  }
  await page.reload();await rendered(page);expect((await items(page,doc.id)).map(a=>a.id).sort()).toEqual(objects.map(a=>a.id).sort())
  expect(await(await page.request.get(`/api/v1/documents/${doc.id}/content`)).body()).toEqual(bytes)
  await group(page,'阅读');await expect(page.locator('.drawing-overlay.erasing')).toHaveCount(0)
  await expect(page.locator('.drawing-object').first()).toHaveCSS('pointer-events','none')
})

test('B2 all seven objects share list toolbar and keyboard deletion',async({page})=>{
  test.setTimeout(120000)
  const {doc,objects}=await deletionObjects(page)
  await group(page,'插入');await button(page,'批注列表').click()
  for(const a of objects) {
    const card=page.locator(`[data-list-annotation="${a.id}"]`)
    await card.getByRole('button',{name:'删除',exact:true}).click()
    await expect.poll(async()=> (await items(page,doc.id)).some(item=>item.id===a.id)).toBe(false)
    await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
    await card.locator('.annotation-card-main').click();await button(page,'删除选中批注').click()
    await expect.poll(async()=> (await items(page,doc.id)).some(item=>item.id===a.id)).toBe(false)
    await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
    await card.locator('.annotation-card-main').click();await page.getByLabel('PDF 阅读区域',{exact:true}).focus();await page.keyboard.press('Delete')
    await expect.poll(async()=> (await items(page,doc.id)).some(item=>item.id===a.id)).toBe(false)
    await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
  }
})

test('B2 all seven objects: live creation, local properties, save/cancel, list, undo/redo and refresh',async({page},info)=>{
  const {doc,bytes}=await setup(page);await group(page,'批注');await draw(page,'手绘');await expect.poll(async()=> (await items(page,doc.id)).length).toBe(1)
  await button(page,'选择批注').click();let all=await items(page,doc.id);expect(all[0]).toMatchObject({type:'ink',style:{lineWidth:2,opacity:1}})
  await group(page,'形状')
  for(const [i,type] of ['矩形','圆形','椭圆形'].entries()){
    await draw(page,type);await expect(page.locator('dialog[open]')).toHaveCount(0);await expect(page.locator('.drawing-controls')).toBeVisible()
    await page.getByLabel('编辑批注颜色',{exact:true}).fill('#123456');await page.getByLabel('批注线宽',{exact:true}).fill('3');await page.getByLabel('批注透明度',{exact:true}).fill('0.65');await page.getByLabel('启用填充',{exact:true}).check();await page.getByLabel('填充颜色',{exact:true}).fill('#E8D9D9')
    expect((await items(page,doc.id)).length).toBe(i+1);await save(page,doc.id,i+2)
  }
  const circle=(await items(page,doc.id)).find(a=>a.type==='circle');expect(circle.geometry.rect.width*612/(circle.geometry.rect.height*792)).toBeCloseTo(1,5)
  await draw(page,'矩形');await button(page,'取消').click();expect((await items(page,doc.id)).length).toBe(4)
  await group(page,'插入');await place(page,'水印');await page.getByLabel('水印内容',{exact:true}).fill('仅当前页 WATERMARK');await page.getByLabel('水印角度',{exact:true}).fill('-30');await page.getByLabel('批注字号',{exact:true}).fill('24');await page.screenshot({path:info.outputPath('b2-watermark-editor.png')});await save(page,doc.id,5)
  await place(page,'图片');await save(page,doc.id,6)
  await button(page,'签名').click();await button(page,'清空').focus();await page.keyboard.press('Escape');await expect(page.getByLabel('创建视觉签名',{exact:true})).toHaveCount(0);await button(page,'签名').click();const pad=page.getByLabel('签名画布',{exact:true}),r=(await pad.boundingBox())!;await page.mouse.move(r.x+30,r.y+70);await page.mouse.down();await page.mouse.move(r.x+130,r.y+40,{steps:20});await page.mouse.move(r.x+210,r.y+90,{steps:20});await page.mouse.up();await page.screenshot({path:info.outputPath('b2-signature-pad.png')});await button(page,'✓ 放置签名').click();await expect(page.getByLabel('创建视觉签名',{exact:true})).toHaveCount(0)
  const paper=(await page.locator('[data-page="1"]').boundingBox())!;await page.mouse.move(paper.x+300,paper.y+420);await expect(page.locator('[data-drawing="preview"]')).toHaveCount(1);await page.mouse.click(paper.x+300,paper.y+420);await save(page,doc.id,7)
  all=await items(page,doc.id);expect(new Set(all.map(a=>a.type))).toEqual(new Set(['ink','rectangle','circle','ellipse','watermark','image','signature']))
  await button(page,'批注列表').click();await expect(page.locator('.annotation-card')).toHaveCount(7);await page.screenshot({path:info.outputPath('b2-all-objects.png')})
  await button(page,'撤销批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(6);await button(page,'重做批注').click();await expect.poll(async()=> (await items(page,doc.id)).length).toBe(7)
  await page.reload();await rendered(page);expect((await items(page,doc.id)).map(a=>a.type).sort()).toEqual(all.map(a=>a.type).sort());await expect(page.locator('.drawing-selection')).toHaveCount(0)
  expect(await (await page.request.get(`/api/v1/documents/${doc.id}/content`)).body()).toEqual(bytes)
})

test('B2 geometry follows pointer, keeps ratios, previews edits and lets native reading through',async({page},info)=>{
  const {doc}=await setup(page);await group(page,'形状');await draw(page,'圆形');await save(page,doc.id,1);let item=(await items(page,doc.id))[0]
  await button(page,'选择批注').click();const shape=page.locator(`[data-drawing="${item.id}"]`);const b=(await shape.boundingBox())!;await page.mouse.click(b.x+b.width,b.y+b.height/2);await expect(shape.locator('[data-handle]')).toHaveCount(4)
  // The center of the selected frame is a drag surface.
  const frame=(await shape.locator('.drawing-selection').boundingBox())!;const beforeMove=(await shape.boundingBox())!;await page.mouse.move(frame.x+frame.width/2,frame.y+frame.height/2);await page.mouse.down();await page.mouse.move(frame.x+frame.width/2+25,frame.y+frame.height/2+20,{steps:6});await expect(shape).toHaveClass(/drag-preview/);expect((await shape.boundingBox())!.x-beforeMove.x).toBeCloseTo(25,0);await page.mouse.up()
  await expect.poll(async()=> (await items(page,doc.id))[0].version).toBe(2)
  const h=shape.locator('[data-handle="se"]'),hb=(await h.boundingBox())!;await page.mouse.move(hb.x+hb.width/2,hb.y+hb.height/2);await page.mouse.down();await page.mouse.move(hb.x+hb.width/2+40,hb.y+hb.height/2+12,{steps:6});await page.mouse.up();await expect.poll(async()=> (await items(page,doc.id))[0].version).toBe(3)
  item=(await items(page,doc.id))[0];expect(item.geometry.rect.width*612/item.geometry.rect.height/792).toBeCloseTo(1,5)
  await button(page,'编辑选中批注').click();await page.getByLabel('编辑批注颜色',{exact:true}).fill('#9B0000');await expect(shape.locator('ellipse')).toHaveAttribute('stroke','#9b0000');await page.getByLabel('编辑批注颜色',{exact:true}).press('Escape');expect((await items(page,doc.id))[0].color).toBe(item.color)
  for(const n of [50,200,500,100]){await zoom(page,n);const box=(await shape.locator('ellipse').boundingBox())!;expect(box.width/box.height).toBeCloseTo(1,2)}
  for(const label of ['单页切换','双页并排','单页连续滚动']){await page.locator('.reader-view-select').click();await page.getByRole('option',{name:label,exact:true}).click();await rendered(page);await expect(shape).toBeAttached()}
  await group(page,'阅读');await expect(shape.locator('[data-handle]')).toHaveCount(0);await expect(shape).toHaveCSS('pointer-events','none')
  const span=page.locator('[data-page="1"] .textLayer span').first();await span.scrollIntoViewIfNeeded();const t=(await span.boundingBox())!;await page.mouse.move(t.x+1,t.y+t.height/2);await page.mouse.down();await page.mouse.move(t.x+t.width-1,t.y+t.height/2,{steps:12});await page.mouse.up();expect(await page.evaluate(()=>window.getSelection()?.toString())).toContain('B2')
  await page.screenshot({path:info.outputPath('b2-reading.png')})
})

test('B2 pointercancel, upload errors, failed save draft, CAS and document switch protection',async({page})=>{
  const {doc,token}=await setup(page);const other=await(await upload(page.request,token,readerPdf('other B2'))).json()
  await group(page,'批注');await button(page,'手绘').click();const overlay=page.locator('[data-page="1"] .drawing-overlay'),b=(await overlay.boundingBox())!;await page.mouse.move(b.x+100,b.y+150);await page.mouse.down();await page.mouse.move(b.x+160,b.y+190,{steps:10});await page.evaluate(()=>{const el=document.querySelector('[data-page="1"] .drawing-overlay')!;el.dispatchEvent(new PointerEvent('pointercancel',{bubbles:true,pointerId:1}))});await page.mouse.up();await expect(page.locator('[data-drawing^="ink-preview"]')).toHaveCount(0);expect(await items(page,doc.id)).toHaveLength(0)
  await group(page,'插入');let held:any
  await page.route(`**/documents/${doc.id}/reader-assets`,route=>{held=route})
  await button(page,'图片').click();await page.getByLabel('选择本地图片',{exact:true}).setInputFiles({name:'cancel.png',mimeType:'image/png',buffer:await imageFile(page)})
  await expect.poll(()=>!!held).toBe(true);await expect(page.getByRole('status').filter({hasText:'正在安全校验图片'})).toBeVisible();await button(page,'× 取消').click();await held.abort().catch(()=>{});await page.unroute(`**/documents/${doc.id}/reader-assets`);await expect(page.getByRole('status').filter({hasText:'正在安全校验图片'})).toHaveCount(0)
  await button(page,'图片').click();await page.getByLabel('选择本地图片',{exact:true}).setInputFiles({name:'bad.png',mimeType:'image/png',buffer:Buffer.from('not png')});await expect(page.getByRole('status').filter({hasText:'请选择可完整解码'})).toBeVisible();await page.getByRole('link',{name:'文献管理',exact:true}).click();await expect(page).toHaveURL(new RegExp(doc.id));await button(page,'× 取消').click()
  await group(page,'形状');await draw(page,'矩形');let fail=true;await page.route(`**/documents/${doc.id}/annotations`,r=>r.request().method()==='POST' && fail?r.abort('failed'):r.continue());await button(page,'保存批注').click();await expect(page.getByRole('alert')).toContainText('批注未保存');await expect(page.locator('.drawing-controls')).toBeVisible();await button(page,'阅读').click();await expect(page.locator('.drawing-controls')).toBeVisible();await page.getByRole('link',{name:'文献管理',exact:true}).click();await expect(page).toHaveURL(new RegExp(doc.id));fail=false;await button(page,'保存批注').click();await expect(page.locator('.drawing-controls')).toHaveCount(0)
  const stale=(await(await page.request.get(`/api/v1/documents/${doc.id}/annotations`)).json()).annotationRevision
  const item=(await items(page,doc.id))[0];await page.request.patch(`/api/v1/documents/${doc.id}/annotations/${item.id}`,{headers:{Origin:origin,'X-CSRF-Token':token},data:{commandId:crypto.randomUUID(),baseRevision:stale,version:item.version,changes:{color:'#6395CF'}}})
  await draw(page,'椭圆形');await button(page,'保存批注').click();await expect(page.getByRole('alert')).toContainText('并发冲突');await expect(page.locator('.drawing-controls')).toBeVisible();expect(await page.evaluate(()=>Object.keys(sessionStorage).some(k=>k.includes('litera:annotations:')))).toBe(true)
  await button(page,'载入服务端批注并保留草稿备份').click();await expect(page.locator('.drawing-controls')).toHaveCount(0);await page.goto(`/reader/${other.id}`);await rendered(page);await expect(page.locator('[data-drawing]')).toHaveCount(0)
})


test('B2 cross-page ink, intrinsic CropBox rotation, mixed sizes and cancelled assets',async({page},info)=>{
  const {doc}=await setup(page);await zoom(page,50);await group(page,'批注');await button(page,'手绘').click()
  const first=(await page.locator('[data-page="1"]').boundingBox())!,second=(await page.locator('[data-page="2"]').boundingBox())!
  await page.mouse.move(first.x+100,first.y+330);await page.mouse.down();await page.mouse.move(first.x+130,first.y+380,{steps:8});await page.mouse.move(second.x+100,second.y+30,{steps:10});await page.mouse.move(second.x+140,second.y+70,{steps:8});await expect(page.locator('[data-drawing^="ink-preview"]')).toHaveCount(2);await page.mouse.up()
  await expect.poll(async()=> (await items(page,doc.id)).length).toBe(2);expect((await items(page,doc.id)).map(a=>a.pageNumber).sort()).toEqual([1,2]);await expect(page.locator('[data-drawing^="ink-preview"]')).toHaveCount(0)
  await button(page,'选择批注').click();const input=page.getByLabel('当前页码',{exact:true});await input.fill('3');await input.press('Enter');await rendered(page,3);await zoom(page,100,3);await rendered(page,3)
  await group(page,'形状');await draw(page,'圆形',3);await save(page,doc.id,3)
  const circle=(await items(page,doc.id)).find(a=>a.type==='circle');expect(circle.pageNumber).toBe(3);expect(circle.geometry.rect.width*580/(circle.geometry.rect.height*740)).toBeCloseTo(1,5)
  const el=page.locator(`[data-drawing="${circle.id}"] ellipse`);expect((await el.boundingBox())!.width/(await el.boundingBox())!.height).toBeCloseTo(1,2)
  await draw(page,'椭圆形',3);await save(page,doc.id,4);await page.screenshot({path:info.outputPath('b2-rotated-crop.png')})
  await group(page,'插入');await button(page,'图片').click();await page.getByLabel('选择本地图片',{exact:true}).setInputFiles({name:'sample.jpg',mimeType:'image/jpeg',buffer:await imageFile(page,'image/jpeg')});await expect(button(page,'图片')).toHaveAttribute('aria-pressed','true')
  expect((await(await page.request.get(`/api/v1/documents/${doc.id}/reader-assets`)).json()).items).toHaveLength(1)
  await page.getByLabel('PDF 阅读区域',{exact:true}).focus();await page.keyboard.press('Escape');await expect.poll(async()=> (await(await page.request.get(`/api/v1/documents/${doc.id}/reader-assets`)).json()).items.length).toBe(0)
  expect(await items(page,doc.id)).toHaveLength(4)
})


test('B2 every object moves/resizes in its group and image validation failure can replace asset',async({page})=>{
  const {doc,token}=await setup(page)
  const headers={Origin:origin,'X-CSRF-Token':token},base=`/api/v1/documents/${doc.id}`
  const image=await(await page.request.post(base+'/reader-assets',{headers,multipart:{file:{name:'asset.png',mimeType:'image/png',buffer:await imageFile(page)}}})).json()
  let revision=0
  const objects:any[]=[]
  for(const type of ['ink','rectangle','circle','ellipse','signature','watermark','image']){
    const id=crypto.randomUUID(),rect={x:.2,y:.3,width:.25,height:type==='circle'?.25*612/792:['image','signature'].includes(type)?.25*612/792/2:.1}
    const annotation={id,type,schemaVersion:1,pageNumber:1,geometry:type==='ink'?{kind:'points',pageNumber:1,points:[{x:.2,y:.3},{x:.3,y:.35},{x:.45,y:.4}]}:{kind:'box',pageNumber:1,rect,rotation:0},position:null,style:{opacity:.9,lineWidth:2,fontSize:24},assetId:['image','signature'].includes(type)?image.assetId:null,selectedText:null,content:type==='watermark'?'WATERMARK':null,color:'#9B0000',zIndex:0}
    const response=await page.request.post(base+'/annotations',{headers,data:{commandId:crypto.randomUUID(),baseRevision:revision++,annotation}});expect(response.status(),type+': '+await response.text()).toBe(201);objects.push((await response.json()).annotation)
  }
  await page.reload();await rendered(page);await zoom(page,100);await button(page,'批注列表').click()
  for(const a of objects){
    const card=page.locator(`[data-list-annotation="${a.id}"]`);await card.getByRole('button',{name:'编辑',exact:true}).click();await expect(page.locator('.drawing-controls')).toBeVisible()
    const shape=page.locator(`[data-drawing="${a.id}"]`),frame=shape.locator('.drawing-selection');await frame.scrollIntoViewIfNeeded();const r=(await frame.boundingBox())!
    await page.mouse.move(r.x+r.width/2,r.y+r.height/2);await page.mouse.down();await page.mouse.move(r.x+r.width/2+15,r.y+r.height/2+12,{steps:5});await expect(shape).toHaveClass(/drag-preview/);await page.mouse.up()
    const h=shape.locator('[data-handle="se"]'),b=(await h.boundingBox())!;await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2+20,b.y+b.height/2+15,{steps:5});await page.mouse.up();await page.getByLabel('批注透明度',{exact:true}).fill('0.6');await save(page,doc.id,7)
    const after=(await items(page,doc.id)).find(x=>x.id===a.id);expect(after.version).toBe(2);expect(after.style.opacity).toBe(.6);expect(after.geometry).not.toEqual(a.geometry)
    if(['circle','image','signature'].includes(a.type)){const rect=after.geometry.rect;expect(rect.width*612/rect.height/792).toBeCloseTo(a.type==='circle'?1:2,5)}
  }
  await group(page,'插入');await place(page,'图片');let reject=true
  const commands:string[]=[];await page.route(`**/documents/${doc.id}/annotations`,route=>{if(route.request().method()!=='POST')return route.continue();commands.push(route.request().postDataJSON().commandId);return reject?route.fulfill({status:422,json:{error:{code:'ASSET_UNAVAILABLE',message:'图片资产已失效，请重新上传'}}}):route.continue()})
  await button(page,'保存批注').click();await expect(page.locator('.annotation-error')).toContainText('图片资产已失效');await button(page,'更换图片').click();await page.getByLabel('选择本地图片',{exact:true}).setInputFiles({name:'replacement.png',mimeType:'image/png',buffer:await imageFile(page)})
  await expect(page.getByRole('status').filter({hasText:'正在安全校验图片'})).toHaveCount(0);reject=false;await button(page,'保存批注').click();await expect(page.locator('.drawing-controls')).toHaveCount(0);expect(await items(page,doc.id)).toHaveLength(8);expect(new Set(commands).size).toBe(2)
})


test.describe('B2 physical PDF units at DPR2',()=>{
  test.use({deviceScaleFactor:2})
  test('B2 UserUnit preserves physical pen width and page coordinates',async({page},info)=>{
    const token=await openLibrary(page),doc=await(await upload(page.request,token,readerPdf('UserUnit B2',1,false,{userUnit:2}))).json();await page.goto(`/reader/${doc.id}`);await rendered(page);await zoom(page,50);await group(page,'批注');await draw(page,'手绘');await expect.poll(async()=> (await items(page,doc.id)).length).toBe(1)
    const ink=(await items(page,doc.id))[0],path=page.locator(`[data-drawing="${ink.id}"] path`);await expect(path).toHaveAttribute('stroke-width','1')
    const r=(await page.locator('[data-page="1"]').boundingBox())!,box=(await path.boundingBox())!,xs=ink.geometry.points.map((p:any)=>p.x),ys=ink.geometry.points.map((p:any)=>p.y)
    const error=Math.max(Math.abs(box.x-r.x-Math.min(...xs)*r.width),Math.abs(box.y-r.y-Math.min(...ys)*r.height));expect(error).toBeLessThan(1)
    await group(page,'形状');await draw(page,'圆形');await save(page,doc.id,2);const circle=(await items(page,doc.id)).find(a=>a.type==='circle');await expect(page.locator(`[data-drawing="${circle.id}"] ellipse`)).toHaveAttribute('stroke-width','1');expect(circle.geometry.rect.width*612/(circle.geometry.rect.height*792)).toBeCloseTo(1,5)
    console.log('B2 DPR2 UserUnit2 ink coordinate CSS error',error);await page.screenshot({path:info.outputPath('b2-user-unit-dpr2.png')})
  })
})
