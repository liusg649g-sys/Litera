export const clampZoom = (value: number) => Math.min(5, Math.max(.5, value))
// Shared by CSS and navigation/fit calculations through ReaderPage's variables.
export const PAGE_PADDING = 12, PAGE_GAP = 12
export function fitZoom(sizes: { width: number; height: number }[], width: number, height: number, mode: string) {
  const total = sizes.reduce((n, s) => n + s.width, 0)
  const tallest = Math.max(...sizes.map(s => s.height))
  return clampZoom(mode === 'fit-width' ? (width - PAGE_PADDING * 2 - Math.max(0, sizes.length - 1) * PAGE_GAP) / total : (height - PAGE_PADDING * 2) / tallest)
}
