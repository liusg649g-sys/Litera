import type { SelectionPosition } from './context'

export interface SourceHighlightRequest { token: number; position: SelectionPosition }
export interface SourceHighlightResult { token: number; pageNumber: number; status: 'exact' | 'page-only'; reason?: string }
export interface SourceTextPart { item: number; start: number; end: number }

const normalizedText = (value: string) => value.replace(/\r\n?/g, '\n').trim()

export function reliableSourcePosition(positions: readonly SelectionPosition[], pageNumber: number): SelectionPosition | null {
  const position = positions.find(item => item.pageNumber === pageNumber)
  if (!position || !position.textQuote.trim() || !position.rects.length || !position.textRanges?.length) return null
  if (position.rects.some(rect => ![rect.x, rect.y, rect.width, rect.height].every(Number.isFinite)
    || rect.x < 0 || rect.y < 0 || rect.width <= 0 || rect.height <= 0
    || rect.x + rect.width > 1.000001 || rect.y + rect.height > 1.000001)) return null
  let previousItem = -1, previousEnd = -1
  for (const range of position.textRanges) {
    if (![range.item, range.start, range.end].every(Number.isInteger) || range.item < 0 || range.start < 0 || range.end <= range.start) return null
    if (range.item < previousItem || (range.item === previousItem && range.start < previousEnd)) return null
    previousItem = range.item; previousEnd = range.end
  }
  return JSON.parse(JSON.stringify(position)) as SelectionPosition
}

export function validateSourceTextRanges(position: SelectionPosition, items: readonly string[], breaksAfter: readonly boolean[]) {
  const parts: SourceTextPart[] = []
  let reconstructed = ''
  for (const saved of position.textRanges || []) {
    const value = items[saved.item]
    if (typeof value !== 'string' || saved.start < 0 || saved.end <= saved.start || saved.end > value.length) return { ok: false as const, reason: '保存的字符范围与当前文字层不一致。' }
    parts.push({ item: saved.item, start: saved.start, end: saved.end })
    reconstructed += value.slice(saved.start, saved.end)
    if (breaksAfter[saved.item]) reconstructed += '\n'
  }
  if (!parts.length) return { ok: false as const, reason: '来源没有可复核的字符范围。' }
  if (normalizedText(reconstructed) !== normalizedText(position.textQuote)) return { ok: false as const, reason: '当前文字层无法逐字复核保存的原文。' }
  return { ok: true as const, parts, reconstructed }
}
