import { describe, it, expect } from 'vitest'
import { clampSidebar, contentUrl, sizeLabel } from '../src/library'
describe('library UI boundaries', () => {
  it('keeps drag and keyboard widths in the supported range', () => {
    expect(clampSidebar(120)).toBe(180)
    expect(clampSidebar(240)).toBe(240)
    expect(clampSidebar(900)).toBe(320)
  })
  it('uses authenticated stable-id content URLs without exposing storage paths', () => {
    expect(contentUrl('document/id')).toBe('/api/v1/documents/document%2Fid/content')
    expect(contentUrl('document', true)).toBe('/api/v1/documents/document/content?download=true')
    expect(sizeLabel(50 * 1024 * 1024)).toBe('50.0 MiB')
    expect(sizeLabel(400)).toBe('400 B')
  })
})
