import { test, expect } from '@playwright/test'
import type { Page } from '@playwright/test'
import { openLibrary, upload } from './library-fixtures'
import { readerPdf } from './reader-fixtures'
async function rendered(page: Page, n = 1) { await expect(page.locator(`.pdf-page[data-page="${n}"]`)).toHaveAttribute('data-status', '已渲染') }
async function view(page: Page, label: string) { await page.locator('.reader-view-select').click(); await page.getByRole('option',{name:label,exact:true}).click() }
async function preset(page: Page, label: string) { await page.getByRole('button',{name:'缩放预设',exact:true}).click(); await page.getByRole('menuitem',{name:label,exact:true}).click(); await rendered(page, Number(await page.getByLabel('当前页码',{exact:true}).inputValue())) }
async function metrics(page: Page) {
  return page.evaluate(() => {
    const root = document.querySelector<HTMLElement>('.pdf-viewport')!, pages = root.querySelector<HTMLElement>('.pdf-pages')!, paper = root.querySelector<HTMLElement>('.pdf-page')!
    const style = getComputedStyle(pages), r = paper.getBoundingClientRect()
    return { clientWidth:root.clientWidth, clientHeight:root.clientHeight, scrollWidth:root.scrollWidth, scrollHeight:root.scrollHeight,
      contentWidth:pages.getBoundingClientRect().width, pageWidth:r.width,pageHeight:r.height,padding:style.padding,gap:style.gap,
      top:r.top-root.getBoundingClientRect().top, brand:document.querySelector('.reader-brandbar')!.getBoundingClientRect().height,
      tabs:document.querySelector('.workspace-tabs')!.getBoundingClientRect().height, toolbar:document.querySelector('.reader-main-toolbar')!.getBoundingClientRect().height }
  })
}
test('compact bars and fit-height use the real viewport without artificial overflow',async({page})=>{
  const token=await openLibrary(page), doc=await(await upload(page.request,token,readerPdf('Layout',7,false,{outline:true}),'Layout.pdf')).json()
  await expect(page.locator('.library-header .brand')).toHaveCSS('font-size','20px');await expect(page.locator('.library-workspace')).toHaveCSS('font-size','12px')
  await page.goto(`/reader/${doc.id}`);await rendered(page);await view(page,'单页切换');await preset(page,'适应高度')
  const size=await metrics(page);console.log('Reader layout metrics',JSON.stringify(size))
  expect(size.brand).toBe(48);expect(size.tabs).toBe(40);expect(size.toolbar).toBe(40)
  expect(size.padding).toBe('12px');expect(size.gap).toBe('12px')
  expect(size.clientHeight-size.pageHeight).toBeCloseTo(24,0)
  expect(size.scrollWidth).toBeLessThanOrEqual(size.clientWidth)
  await expect(page.locator('.reader-footer')).toHaveCount(0)
  await expect(page.locator('.reader-brandbar .brand')).toHaveCSS('font-size','20px');await expect(page.locator('.reader-workspace')).toHaveCSS('font-size','12px')
  expect(await page.locator('.pdf-viewport').evaluate(el=>el.getBoundingClientRect().bottom)).toBe(768)
  await page.getByRole('button',{name:'批注',exact:true}).click();await expect(page.locator('.reader-secondary')).toHaveCSS('height','40px')
  await expect.poll(async()=>{const m=await metrics(page);return m.clientHeight-m.pageHeight}).toBeCloseTo(24,0)
  expect((await metrics(page)).clientHeight).toBe(size.clientHeight-40)
  await page.getByRole('button',{name:'阅读',exact:true}).click();await expect(page.locator('.reader-secondary')).toHaveCount(0)
  await expect.poll(async()=>(await metrics(page)).clientHeight).toBe(size.clientHeight)
  await page.screenshot({path:'test-results/a2-ux-compact-fit-height.png'})
})

test('SVG chevrons align; pointer arrows have no frame while Tab retains a visible focus indicator',async({page})=>{
  const token=await openLibrary(page), doc=await(await upload(page.request,token,readerPdf('Focus',7,false,{outline:true}),'Focus.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await view(page,'单页切换')
  const root=page.getByLabel('PDF 阅读区域',{exact:true})
  await root.click({position:{x:5,y:40}});await expect(root).toBeFocused();await page.keyboard.press('ArrowRight');await rendered(page,2)
  await expect(root).toHaveCSS('outline-style','none')
  await page.getByRole('button',{name:'下载 PDF',exact:true}).focus();await page.keyboard.press('Tab');await expect(root).toBeFocused();await expect(root).toHaveCSS('outline-style','solid')
  await page.keyboard.press('ArrowLeft');await rendered(page)
  const input=page.getByLabel('当前页码',{exact:true});await input.focus();await input.press('ArrowRight');await expect(input).toHaveValue('1')
  await root.click({position:{x:5,y:40}});await expect(root).toHaveCSS('outline-style','none')
  await page.getByRole('button',{name:'展开文献导航',exact:true}).click();await page.getByRole('button',{name:'大纲',exact:true}).click()
  await page.getByRole('button',{name:'展开 Chapter',exact:true}).click()
  const toggle=page.getByRole('button',{name:'折叠 Chapter',exact:true}), zoom=page.getByRole('button',{name:'缩放预设',exact:true})
  for(const button of [toggle,zoom]) {
    const b=(await button.boundingBox())!,svg=(await button.locator('svg').boundingBox())!
    expect(svg.width).toBe(14);expect(svg.height).toBe(14);expect(Math.abs(svg.y+7-b.y-b.height/2)).toBeLessThanOrEqual(1)
    expect(await button.textContent()).toBe('')
  }
  const parent=(await page.getByRole('button',{name:'Chapter',exact:true}).boundingBox())!,child=(await page.getByRole('button',{name:'Child section',exact:true}).boundingBox())!
  expect(child.x-parent.x).toBeGreaterThanOrEqual(20)
  const path=await toggle.locator('path').getAttribute('d');await toggle.click()
  const collapsed=page.getByRole('button',{name:'展开 Chapter',exact:true});await expect(collapsed).toHaveAttribute('aria-expanded','false');expect(await collapsed.locator('path').getAttribute('d')).not.toBe(path)
  await collapsed.click();await expect(page.getByRole('button',{name:'Child section',exact:true})).toBeVisible()
})

test('three modes share 12px spacing; fit responds to resize and true overflow remains scrollable',async({page})=>{
  const token=await openLibrary(page), doc=await(await upload(page.request,token,readerPdf('Spacing',7),'Spacing.pdf')).json()
  await page.goto(`/reader/${doc.id}`);await rendered(page);await preset(page,'适应高度')
  const gap=()=>page.locator('.pdf-page').evaluateAll(nodes=>nodes[1]!.getBoundingClientRect().top-nodes[0]!.getBoundingClientRect().bottom)
  expect(await gap()).toBeCloseTo(12,0)
  for(const mode of ['单页切换','双页并排']) {
    await view(page,mode);await preset(page,'适应宽度')
    const m=await metrics(page);expect(m.padding).toBe('12px');expect(m.gap).toBe('12px');expect(m.scrollWidth).toBeLessThanOrEqual(m.clientWidth)
    if(mode==='双页并排') expect(await page.locator('.pdf-page').evaluateAll(nodes=>nodes[1]!.getBoundingClientRect().left-nodes[0]!.getBoundingClientRect().right)).toBeCloseTo(12,0)
    await preset(page,'适应高度');await expect.poll(async()=>{const m=await metrics(page);return m.clientHeight-m.pageHeight}).toBeCloseTo(24,0)
  }
  const pageNumber=page.getByLabel('当前页码',{exact:true});await pageNumber.fill('3');await pageNumber.press('Enter');await rendered(page,3);await preset(page,'适应高度')
  await expect.poll(()=>page.locator('.pdf-viewport').evaluate(root=>root.clientHeight-Math.max(...[...root.querySelectorAll('.pdf-page')].map(el=>el.getBoundingClientRect().height)))).toBeCloseTo(24,0)
  await pageNumber.fill('1');await pageNumber.press('Enter');await rendered(page)
  await page.setViewportSize({width:1920,height:1080})
  await expect.poll(async()=>{const m=await metrics(page);return m.clientHeight-m.pageHeight}).toBeCloseTo(24,0)
  await page.getByRole('button',{name:'展开文献导航',exact:true}).click();await page.getByRole('button',{name:'搜索文献',exact:true}).click()
  await expect.poll(async()=>{const m=await metrics(page);return m.clientHeight-m.pageHeight}).toBeCloseTo(24,0)
  const input=page.getByLabel('缩放比例',{exact:true});await input.fill('500');await input.press('Enter');await rendered(page)
  const large=await metrics(page);expect(large.scrollWidth).toBeGreaterThan(large.clientWidth)
  expect(await page.locator('.pdf-viewport').evaluate(el=>{el.scrollLeft=200;return el.scrollLeft})).toBeGreaterThan(0)
  await preset(page,'适应宽度');await expect.poll(async()=>{const m=await metrics(page);return m.scrollWidth-m.clientWidth}).toBe(0)
  await page.getByRole('button',{name:'收起文献导航',exact:true}).click();await page.getByRole('button',{name:'关闭搜索',exact:true}).click();await view(page,'单页切换')
  await preset(page,'适应宽度');await rendered(page)
  await page.setViewportSize({width:390,height:844});await expect(page.locator('.reader-main-toolbar')).toHaveCSS('height','40px')
  await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
})
