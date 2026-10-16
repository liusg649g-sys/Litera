import type { NormalizedRect } from './context'
export const boxHandles = ['nw','n','ne','e','se','s','sw','w'] as const
export type BoxHandle = typeof boxHandles[number]
export function resizeBox(r: NormalizedRect, dx: number, dy: number, handle: BoxHandle): NormalizedRect {
  let left=r.x, top=r.y, right=r.x+r.width, bottom=r.y+r.height
  if (handle.includes('w')) left=Math.max(0,Math.min(right-.02,left+dx))
  if (handle.includes('e')) right=Math.min(1,Math.max(left+.02,right+dx))
  if (handle.includes('n')) top=Math.max(0,Math.min(bottom-.02,top+dy))
  if (handle.includes('s')) bottom=Math.min(1,Math.max(top+.02,bottom+dy))
  return { x:left,y:top,width:right-left,height:bottom-top }
}
