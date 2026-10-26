import type { PDFPageProxy } from 'pdfjs-dist'
export const unreliableTextMessage = '无法可靠提取原文：此选区的 PDF 文字编码或映射异常，已阻止翻译。请使用带有效文字映射的 PDF，或经人工核对的 OCR 副本。'
export function textHasUnmappedCharacters(text: string): boolean {
  // Inspect only: never delete, replace, normalize or guess source characters.
  return /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\uFFFD]|\p{Co}|\p{Cs}/u.test(text)
}
const mappings = new WeakMap<PDFPageProxy, Promise<{fonts: Set<string>; items: string[]}>>()
export function pageTextMapping(page: PDFPageProxy) {
  let pending=mappings.get(page)
  if(!pending) {
    pending=page.getTextContent().then(content=>{
      const items=content.items.filter((item):item is import('pdfjs-dist/types/src/display/api').TextItem=>'str' in item)
      const fonts=new Set(items.filter(item=>textHasUnmappedCharacters(item.str)).map(item=>item.fontName))
      return {fonts,items:items.map(item=>item.fontName)}
    })
    mappings.set(page,pending)
  }
  return pending
}
