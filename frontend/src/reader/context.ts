import { shallowRef } from 'vue'
import { viewportToNormalized } from './state'
import type { PDFDocumentProxy } from 'pdfjs-dist'
export interface NormalizedRect { x: number; y: number; width: number; height: number }
export interface SelectionPosition { pageNumber: number; rects: NormalizedRect[]; textQuote: string }
export interface Citation { documentId: string; extractionVersion: string; chunkId: string; pageNumber: number; quote: string }
export interface NoteDraft { documentId: string; pageNumber: number | null; annotationId: string | null; title: string; content: string; sourceType: 'manual' | 'selection' | 'translation' | 'ai'; sourceId: string | null; originalText: string | null; translatedText: string | null; citations: Citation[] }
export interface ReaderContext { documentId: string; pageNumber: number; selectedText: string; selectionPosition: SelectionPosition[] | null; annotationId: string | null; contextRevision: number }
export type ReaderEvent = 'context-change' | 'selection-change' | 'document-change' | 'context-cleared'
let revision = 0
export const readerContext = shallowRef<Readonly<ReaderContext> | null>(null)
const listeners = new Set<(event: ReaderEvent, context: Readonly<ReaderContext> | null) => void>()
export function subscribeReaderContext(callback: (event: ReaderEvent, context: Readonly<ReaderContext> | null) => void) { listeners.add(callback); return () => { listeners.delete(callback) } }
export function publishContext(event: ReaderEvent, value?: Omit<ReaderContext, 'contextRevision' | 'annotationId'>) {
  revision++
  const snapshot = value ? structuredClone({ ...value, annotationId: null, contextRevision: revision }) : null
  if (snapshot) { snapshot.selectionPosition?.forEach(p => { p.rects.forEach(Object.freeze); Object.freeze(p.rects); Object.freeze(p) }); if (snapshot.selectionPosition) Object.freeze(snapshot.selectionPosition); Object.freeze(snapshot) }
  readerContext.value = snapshot
  window.dispatchEvent(new CustomEvent(`litera:reader:${event}`, { detail: snapshot }))
  for (const callback of listeners) { try { callback(event, snapshot) } catch (error) { console.warn('[Litera] ReaderContext subscriber failed', error) } }
}
export async function readSelection(pdf: PDFDocumentProxy, root: HTMLElement): Promise<{ selectedText: string; selectionPosition: SelectionPosition[] | null }> {
  const selection = window.getSelection()
  if (!selection || selection.isCollapsed || !selection.rangeCount || !root.contains(selection.anchorNode) || !root.contains(selection.focusNode)) return { selectedText: '', selectionPosition: null }
  const range = selection.getRangeAt(0).cloneRange(), positions: SelectionPosition[] = []
  // Intersect each text span, never include canvas, page margins or search UI.
  let selectedText = ''
  for (const element of root.querySelectorAll<HTMLElement>('.pdf-page')) {
    const spans = element.querySelectorAll<HTMLElement>('.textLayer span'), rects: NormalizedRect[] = []
    let textQuote = ''
    if (![...spans].some(span => span.firstChild?.nodeType === Node.TEXT_NODE && range.intersectsNode(span.firstChild))) continue
    const number = Number(element.dataset.page), page = await pdf.getPage(number)
    const bounds = element.getBoundingClientRect(), viewport = page.getViewport({ scale: bounds.width / page.getViewport({ scale: 1 }).width })
    for (const span of spans) {
      const node = span.firstChild
      if (!node || node.nodeType !== Node.TEXT_NODE || !range.intersectsNode(node)) continue
      const part = document.createRange(); part.selectNodeContents(node)
      if (range.startContainer === node) part.setStart(node, range.startOffset)
      if (range.endContainer === node) part.setEnd(node, range.endOffset)
      textQuote += part.toString() + (span.nextSibling?.nodeName === 'BR' ? '\n' : '')
      for (const rect of part.getClientRects()) {
        const points = [[rect.left,rect.top],[rect.right,rect.top],[rect.left,rect.bottom],[rect.right,rect.bottom]].map(([x,y]) => viewportToNormalized(viewport, x! - bounds.left, y! - bounds.top))
        const clamp = (value: number) => Math.max(0, Math.min(1, value))
        const x = clamp(Math.min(...points.map(p => p.x))), y = clamp(Math.min(...points.map(p => p.y)))
        const width = clamp(Math.max(...points.map(p => p.x))) - x, height = clamp(Math.max(...points.map(p => p.y))) - y
        if (width > 0 && height > 0) rects.push({ x, y, width, height })
      }
    }
    if (rects.length) { positions.push({ pageNumber: number, rects, textQuote: textQuote.trim() }); selectedText += textQuote + '\n' }
  }
  return { selectedText: selectedText.trim(), selectionPosition: positions.length ? positions : null }
}
