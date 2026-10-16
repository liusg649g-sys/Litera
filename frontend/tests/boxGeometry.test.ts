import { describe, expect, it } from 'vitest'
import { boxHandles, resizeBox } from '../src/reader/boxGeometry'
describe('free text box handles', () => {
  it('keeps the opposite edges fixed for every handle and does not mutate the source', () => {
    const r={x:.2,y:.3,width:.4,height:.2}
    for(const handle of boxHandles) {
      const result=resizeBox(r,.03,.04,handle)
      expect(result.x).toBeCloseTo(handle.includes('w') ? .23 : .2)
      expect(result.y).toBeCloseTo(handle.includes('n') ? .34 : .3)
      expect(result.x+result.width).toBeCloseTo(handle.includes('e') ? .63 : .6)
      expect(result.y+result.height).toBeCloseTo(handle.includes('s') ? .54 : .5)
    }
    expect(r).toEqual({x:.2,y:.3,width:.4,height:.2})
  })
  it('constrains all handles to the page and prevents inversion', () => {
    for(const handle of boxHandles) for(const delta of [-20,20]) {
      const r=resizeBox({x:.2,y:.3,width:.4,height:.2},delta,delta,handle)
      expect(r.x).toBeGreaterThanOrEqual(0);expect(r.y).toBeGreaterThanOrEqual(0)
      expect(r.x+r.width).toBeLessThanOrEqual(1);expect(r.y+r.height).toBeLessThanOrEqual(1)
      expect(r.width).toBeGreaterThanOrEqual(.019999);expect(r.height).toBeGreaterThanOrEqual(.019999)
    }
  })
})
