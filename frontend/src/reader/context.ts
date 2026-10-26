import { shallowReadonly, shallowRef } from 'vue'
import { viewportToNormalized } from './state'
import { pageTextMapping, textHasUnmappedCharacters, unreliableTextMessage } from './textQuality'
import type { PDFDocumentProxy } from 'pdfjs-dist'
export interface NormalizedRect { x: number; y: number; width: number; height: number; baseline?: number }
export interface SelectionPosition { pageNumber: number; rects: NormalizedRect[]; textQuote: string; textRanges?: { item: number; start: number; end: number }[] }
export interface Citation { documentId: string; extractionVersion: string; chunkId: string; pageNumber: number; quote: string }
export interface NoteDraft { documentId: string; pageNumber: number | null; annotationId: string | null; title: string; content: string; sourceType: 'manual' | 'selection' | 'translation' | 'ai'; sourceId: string | null; originalText: string | null; translatedText: string | null; citations: Citation[] }
export interface ReaderContext { documentId: string; pageNumber: number; selectedText: string; selectionPosition: SelectionPosition[] | null; annotationId: string | null; contextRevision: number; textExtractionIssue?: string | null }
export type ReaderEvent = 'context-change' | 'selection-change' | 'document-change' | 'page-change' | 'context-cleared'
let revision = 0
const currentContext = shallowRef<Readonly<ReaderContext> | null>(null)
export const readerContext = shallowReadonly(currentContext)
const listeners = new Set<(event: ReaderEvent, context: Readonly<ReaderContext> | null) => void>()
export function subscribeReaderContext(callback: (event: ReaderEvent, context: Readonly<ReaderContext> | null) => void, signal?: AbortSignal) {
  const stop = () => { listeners.delete(callback); signal?.removeEventListener('abort', stop) }
  if (!signal?.aborted) { listeners.add(callback); signal?.addEventListener('abort', stop, { once: true }) }
  return stop
}
export function isReaderContextCurrent(value: Pick<ReaderContext, 'documentId' | 'contextRevision'>) {
  return readerContext.value?.documentId === value.documentId && readerContext.value?.contextRevision === value.contextRevision
}
export function publishContext(event: ReaderEvent, value?: Omit<ReaderContext, 'contextRevision' | 'annotationId'> & { annotationId?: string | null }) {
  revision++
  const snapshot = value ? structuredClone({ ...value, annotationId: value.annotationId ?? null, contextRevision: revision }) : null
  if (snapshot) { snapshot.selectionPosition?.forEach(p => { p.rects.forEach(Object.freeze); Object.freeze(p.rects); p.textRanges?.forEach(Object.freeze); if(p.textRanges) Object.freeze(p.textRanges); Object.freeze(p) }); if (snapshot.selectionPosition) Object.freeze(snapshot.selectionPosition); Object.freeze(snapshot) }
  currentContext.value = snapshot
  window.dispatchEvent(new CustomEvent(`litera:reader:${event}`, { detail: snapshot }))
  for (const callback of listeners) { try { callback(event, snapshot) } catch (error) { console.warn('[Litera] ReaderContext subscriber failed', error) } }
}
export async function readSelection(pdf: PDFDocumentProxy, root: HTMLElement): Promise<{ selectedText: string; selectionPosition: SelectionPosition[] | null; textExtractionIssue?: string | null }> {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed || !selection.rangeCount || !root.contains(selection.anchorNode) || !root.contains(selection.focusNode)) return { selectedText: '', selectionPosition: null }
  const range = selection.getRangeAt(0).cloneRange(), positions: SelectionPosition[] = []
  // Intersect each text span, never include canvas, page margins or search UI.
  let selectedText = '', textExtractionIssue: string | undefined
  for (const element of root.querySelectorAll<HTMLElement>('.pdf-page')) {
    const spans = element.querySelectorAll<HTMLElement>('.textLayer span:not(.markedContent)'), rects: NormalizedRect[] = [], textRanges: NonNullable<SelectionPosition['textRanges']> = []
    let textQuote = ''
    if (![...spans].some(span => span.firstChild?.nodeType === Node.TEXT_NODE && range.intersectsNode(span.firstChild))) continue
    const number = Number(element.dataset.page), page = await pdf.getPage(number)
    const mapping = await pageTextMapping(page)
    const bounds = element.getBoundingClientRect(), viewport = page.getViewport({ scale: bounds.width / page.getViewport({ scale: 1 }).width })
    for (const [item, span] of [...spans].entries()) {
      const node = span.firstChild
      if (!node || node.nodeType !== Node.TEXT_NODE || !range.intersectsNode(node)) continue
      const part = document.createRange(); part.selectNodeContents(node)
      // Clip both boundaries even when the browser uses an element boundary rather
      // than a Text node. Never expand a partial native Range to the entire item.
      if (range.compareBoundaryPoints(Range.START_TO_START, part) > 0) part.setStart(range.startContainer, range.startOffset)
      if (range.compareBoundaryPoints(Range.END_TO_END, part) < 0) part.setEnd(range.endContainer, range.endOffset)
      if (part.collapsed || !part.toString()) continue
      const start = part.startContainer === node ? part.startOffset : 0
      const end = part.endContainer === node ? part.endOffset : node.textContent!.length
      const textItem = Number(span.dataset.textItem ?? item)
      if(mapping.fonts.has(mapping.items[textItem] ?? '') || textHasUnmappedCharacters(part.toString())) textExtractionIssue = unreliableTextMessage
      textRanges.push({ item: Number(span.dataset.textItem ?? item), start, end })
      textQuote += part.toString() + (span.nextSibling?.nodeName === 'BR' ? '\n' : '')
      for (const rect of part.getClientRects()) {
        const points = [[rect.left,rect.top],[rect.right,rect.top],[rect.left,rect.bottom],[rect.right,rect.bottom]].map(([x,y]) => viewportToNormalized(viewport, x! - bounds.left, y! - bounds.top))
        const clamp = (value: number) => Math.max(0, Math.min(1, value))
        const x = clamp(Math.min(...points.map(p => p.x))), y = clamp(Math.min(...points.map(p => p.y)))
        const width = clamp(Math.max(...points.map(p => p.x))) - x, height = clamp(Math.max(...points.map(p => p.y))) - y
        if (width > 0 && height > 0) rects.push({ x, y, width, height, baseline: fontBaseline(span) })
      }
    }
    if (rects.length && textQuote.trim()) { positions.push({ pageNumber: number, rects: mergeTextRects(rects, page.view[2]! - page.view[0]!, page.view[3]! - page.view[1]!), textQuote: textQuote.trim(), textRanges }); selectedText += textQuote + '\n' }
  }
  return { selectedText: selectedText.trim(), selectionPosition: positions.length ? positions : null, ...(textExtractionIssue ? {textExtractionIssue} : {}) }
}

const fontMetrics = new Map<string, number>()
let metricCanvas: HTMLCanvasElement | undefined
function fontBaseline(span: HTMLElement) {
  const style = getComputedStyle(span), font = `${style.fontStyle} ${style.fontWeight} 100px ${style.fontFamily}`
  if (fontMetrics.has(font)) return fontMetrics.get(font)!
  const ctx = (metricCanvas ||= document.createElement('canvas')).getContext('2d')!
  ctx.font = font
  const m = ctx.measureText('Hg'), total = m.fontBoundingBoxAscent + m.fontBoundingBoxDescent
  const baseline = total > 0 ? m.fontBoundingBoxAscent / total : .8
  if (fontMetrics.size >= 128) fontMetrics.clear()
  fontMetrics.set(font, baseline); return baseline
}

// Work in unrotated PDF units, not screen axes: intrinsic Rotate/CropBox and zoom
// must not change which fragments form a line. Only bridge a normal word space.
export function mergeTextRects(rects: NormalizedRect[], width: number, height: number): NormalizedRect[] {
  const lines: NormalizedRect[] = []
  for (const r of [...rects].sort((a,b) => a.y-b.y || a.x-b.x)) {
    const h = r.height * height
    const previous = lines.find(p => {
      const ph = p.height * height, overlap = (Math.min(p.y+p.height,r.y+r.height)-Math.max(p.y,r.y))*height
      const gap = (Math.max(p.x,r.x)-Math.min(p.x+p.width,r.x+r.width))*width
      return overlap >= Math.min(h,ph)*.75 && Math.max(h,ph) <= Math.min(h,ph)*1.4 && gap <= Math.min(h,ph)*.55
    })
    if (!previous) { lines.push({ ...r }); continue }
    const baseline = Math.max(previous.y+previous.height*(previous.baseline ?? .8),r.y+r.height*(r.baseline ?? .8))
    const hasBaseline = previous.baseline !== undefined || r.baseline !== undefined
    const right = Math.max(previous.x+previous.width,r.x+r.width), bottom = Math.max(previous.y+previous.height,r.y+r.height)
    previous.x = Math.min(previous.x,r.x); previous.y = Math.min(previous.y,r.y)
    previous.width = right-previous.x; previous.height = bottom-previous.y
    if (hasBaseline) previous.baseline = (baseline-previous.y)/previous.height
  }
  return lines
}
