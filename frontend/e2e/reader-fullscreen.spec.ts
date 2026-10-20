import { test,expect,type Page } from '@playwright/test'
import { openLibrary,upload } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
async function setup(page:Page){
  const token=await openLibrary(page)
  const doc=await(await upload(page.request,token,readerPdf('Fullscreen '+Date.now(),6,true))).json()
  await page.goto(`/reader/${doc.id}`)
  await expect(page.locator('.pdf-page[data-page="1"]')).toHaveAttribute('data-status','已渲染')
}
async function reveal(page:Page){await expect(page.locator('.reader-workspace')).toHaveClass(/reader-fullscreen/);await expect(page.getByRole('button',{name:'退出全屏',exact:true})).toBeEnabled()}
async function exit(page:Page){await page.evaluate(()=>document.exitFullscreen());await expect(page.locator('.reader-workspace')).not.toHaveClass(/reader-fullscreen/);await expect(page.getByRole('button',{name:'全屏阅读',exact:true})).toBeEnabled()}
async function readingPoint(page:Page){return page.getByLabel('PDF 阅读区域',{exact:true}).evaluate(root=>{
  const page=root.querySelector<HTMLElement>('[data-page="3"]')!,r=page.getBoundingClientRect()
  return (root.getBoundingClientRect().top+16-r.top)/r.height
})}

test('fullscreen slides only the brand bar for 200ms and editing tools never overlap content or panels',async({page},info)=>{
  await setup(page)
  await page.locator('.reader-brandbar-slot').evaluate(el=>{
    const frames:number[]=[];(window as any).__brandFrames=frames
    el.addEventListener('transitionrun',(event)=>{
      if((event as TransitionEvent).propertyName!=='height')return
      const sample=()=>{frames.push(el.getBoundingClientRect().height);if(el.getAnimations().some(a=>a.playState==='running'))requestAnimationFrame(sample)}
      requestAnimationFrame(sample)
    })
  })
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click();await reveal(page)
  await expect(page.locator('.reader-brandbar-slot')).toHaveCSS('height','0px')
  await expect(page.locator('.reader-tabs')).toBeVisible()
  await expect(page.locator('.reader-brandbar-slot')).toHaveCSS('transition-duration','0.2s')
  expect(await page.evaluate(()=>(window as any).__brandFrames.some((h:number)=>h>0 && h<48))).toBe(true)
  await page.getByRole('button',{name:'批注',exact:true}).click()
  await page.getByRole('button',{name:'批注列表',exact:true}).click()
  const secondary=(await page.locator('.reader-secondary').boundingBox())!
  const region=(await page.getByLabel('PDF 阅读区域',{exact:true}).boundingBox())!
  const panelHeader=(await page.locator('.reader-panel.right:visible > header').boundingBox())!
  expect(region.y).toBeGreaterThanOrEqual(secondary.y+secondary.height)
  expect(panelHeader.y).toBeGreaterThanOrEqual(secondary.y+secondary.height)
  await expect(page.getByRole('button',{name:'退出全屏',exact:true}).locator('svg path')).toHaveAttribute('d','M4 9h5V4m11 5h-5V4M4 15h5v5m11-5h-5v5')
  await page.screenshot({path:info.outputPath('fullscreen-edit-layout.png'),animations:'disabled'})
  await page.evaluate(()=>(window as any).__brandFrames.length=0)
  await exit(page)
  await expect(page.locator('.reader-brandbar-slot')).toHaveCSS('height','48px')
  await expect(page.locator('.reader-brandbar')).toBeVisible()
  expect(await page.evaluate(()=>(window as any).__brandFrames.some((h:number)=>h>0 && h<48))).toBe(true)
})

for(const view of ['单页连续滚动','单页切换','双页并排'])test(`native fullscreen preserves ${view} and keeps tools in layout`,async({page},info)=>{
  await setup(page)
  await page.locator('.reader-view-select').click();await page.getByRole('option',{name:view,exact:true}).click()
  await page.getByLabel('缩放比例',{exact:true}).fill('100');await page.getByLabel('缩放比例',{exact:true}).press('Enter')
  await page.getByLabel('当前页码',{exact:true}).fill('3');await page.getByLabel('当前页码',{exact:true}).press('Enter')
  await expect(page.locator('.pdf-page[data-page="3"]')).toHaveAttribute('data-status','已渲染')
  await page.getByRole('button',{name:'展开文献导航',exact:true}).click()
  const width=await page.getByLabel('文献导航',{exact:true}).evaluate(el=>el.getBoundingClientRect().width)
  const point=await readingPoint(page)
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click()
  await expect.poll(()=>page.evaluate(()=>document.fullscreenElement?.classList.contains('reader-workspace'))).toBe(true)
  await reveal(page);await expect(page.locator('.reader-brandbar')).toBeHidden();await expect(page.locator('.reader-tabs')).toBeVisible()
  await page.mouse.move(500,500)
  await expect(page.locator('.reader-fullscreen-tools')).toHaveCSS('opacity','1')
  const viewport=page.getByLabel('PDF 阅读区域',{exact:true}),before=await viewport.boundingBox()
  await reveal(page)
  expect(await viewport.boundingBox()).toEqual(before)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('3')
  await expect(page.getByLabel('缩放比例',{exact:true})).toHaveValue('100')
  await expect.poll(async()=>Math.abs(await readingPoint(page)-point)).toBeLessThan(.02)
  await page.getByRole('button',{name:'下载 PDF',exact:true}).first().click()
  await expect(page.getByRole('menuitem',{name:'导出带批注 PDF',exact:true})).toBeVisible()
  expect(await page.locator('.pdf-download-menu:visible').evaluate(el=>!!document.fullscreenElement?.contains(el))).toBe(true)
  await page.mouse.move(500,500)
  await expect(page.locator('.reader-fullscreen-tools')).toHaveCSS('opacity','1')
  await page.screenshot({path:info.outputPath('fullscreen-menu.png'),animations:'disabled'})
  // Download authorization/bytes are covered by C1. Native download UI may
  // itself leave fullscreen; close the menu here to isolate layout retention.
  await viewport.click({position:{x:20,y:100}})
  await reveal(page);await page.getByRole('button',{name:'搜索文献',exact:true}).click()
  await expect(page.locator('.reader-panel.right:visible')).toBeVisible()
  await exit(page)
  await expect(page.getByLabel('当前页码',{exact:true})).toHaveValue('3')
  await expect(page.getByLabel('缩放比例',{exact:true})).toHaveValue('100')
  await expect.poll(async()=>Math.abs(await readingPoint(page)-point)).toBeLessThan(.02)
  expect(await page.getByLabel('文献导航',{exact:true}).evaluate(el=>el.getBoundingClientRect().width)).toBe(width)
  await expect(page.locator('.reader-brandbar')).toBeVisible();await expect(page.locator('.reader-tabs')).toBeVisible()
})

test('fullscreen keeps annotation draft and ignores reader Escape actions without preventing native Escape',async({page})=>{
  await setup(page)
  await page.getByRole('button',{name:'批注',exact:true}).click();await page.getByRole('button',{name:'注释',exact:true}).click()
  await page.locator('.pdf-page[data-page="1"] .annotation-overlay').click({position:{x:180,y:240}})
  await page.getByLabel('批注正文',{exact:true}).fill('全屏前的草稿\n保留')
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click()
  await page.mouse.move(400,500)
  await expect(page.locator('.reader-fullscreen-tools')).toHaveCSS('opacity','1')
  expect(await page.locator('.reader-workspace').evaluate(el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true})))).toBe(true)
  await expect(page.getByLabel('批注正文',{exact:true})).toHaveValue('全屏前的草稿\n保留')
  await exit(page)
  await page.locator('.reader-workspace').evaluate(el=>el.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true})))
  await expect(page.getByLabel('批注正文',{exact:true})).toHaveValue('全屏前的草稿\n保留')
})

test('fullscreen rejection gives a clear message and keeps regular layout',async({page})=>{
  await setup(page)
  await page.locator('.reader-workspace').evaluate(el=>{el.requestFullscreen=()=>Promise.reject(new DOMException('Denied','NotAllowedError'))})
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click()
  await expect(page.getByRole('status').filter({hasText:'无法切换全屏'})).toBeVisible()
  await expect(page.locator('.reader-workspace')).not.toHaveClass(/reader-fullscreen/)
  await expect(page.locator('.reader-brandbar')).toBeVisible()
})

test('narrow fullscreen keeps selects inside fullscreen and has no viewport overflow',async({page})=>{
  await page.setViewportSize({width:700,height:900});await setup(page)
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click();await reveal(page)
  await page.locator('.reader-view-select').click()
  await expect(page.getByRole('option',{name:'双页并排',exact:true})).toBeVisible()
  expect(await page.getByRole('option',{name:'双页并排',exact:true}).evaluate(el=>!!document.fullscreenElement?.contains(el))).toBe(true)
  await page.getByRole('option',{name:'双页并排',exact:true}).click()
  expect(await page.locator('.reader-workspace').evaluate(el=>el.scrollWidth<=el.clientWidth)).toBe(true)
  await exit(page)
  await page.evaluate(()=>Object.defineProperty(document,'fullscreenEnabled',{configurable:true,value:false}))
  await page.getByRole('button',{name:'全屏阅读',exact:true}).click()
  await expect(page.getByRole('status').filter({hasText:'不支持全屏阅读'})).toBeVisible()
})
