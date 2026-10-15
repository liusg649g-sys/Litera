import type { TextItem } from 'pdfjs-dist/types/src/display/api'
export interface SearchPart { item: number; start: number; end: number }
export interface SearchMatch { pageNumber: number; parts: SearchPart[]; snippet: string; id: string }
// NFKC maps ligatures/full-width characters; every normalized UTF-16 unit keeps
// its source item/range. Item boundaries are not word boundaries.
export function findMatches(items: Pick<TextItem, 'str' | 'hasEOL'>[], keyword: string, caseSensitive: boolean, wholeWord: boolean, pageNumber: number): SearchMatch[] {
  let text = ''
  const map: SearchPart[] = []
  for (const [item, value] of items.entries()) {
    let offset = 0
    for (const char of value.str) {
      let normalized = char.normalize('NFKC').replace(/\s/gu, ' '); if (!caseSensitive) normalized = normalized.toLowerCase()
      text += normalized
      for (let i = 0; i < normalized.length; i++) map.push({ item, start: offset, end: offset + char.length })
      offset += char.length
    }
    if (value.hasEOL) { text += ' '; map.push({ item, start: offset, end: offset }) }
  }
  let query = keyword.normalize('NFKC').replace(/\s/gu, ' '); if (!caseSensitive) query = query.toLowerCase()
  if (!query) return []
  const boundaries = new Set<number>()
  if (wholeWord) {
    for (const segment of new Intl.Segmenter('und', { granularity: 'word' }).segment(text)) {
      boundaries.add(segment.index); boundaries.add(segment.index + segment.segment.length)
    }
  }
  const results: SearchMatch[] = []
  for (let at = text.indexOf(query); at !== -1; at = text.indexOf(query, at + Math.max(1, query.length))) {
    const end = at + query.length
    if (wholeWord && (!boundaries.has(at) || !boundaries.has(end))) continue
    const parts: SearchPart[] = []
    for (const source of map.slice(at, end)) {
      if (source.start === source.end) continue
      const previous = parts.at(-1)
      if (previous?.item === source.item) previous.end = source.end
      else parts.push({ ...source })
    }
    results.push({ pageNumber, parts, snippet: text.slice(Math.max(0,at-30), end+60), id: `${pageNumber}-${at}` })
  }
  return results
}
