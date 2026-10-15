import { describe, it, expect, beforeEach } from 'vitest'
import { pageGroup, adjacentPage, readerTabs, clearReaderTabs, openReaderTab, moveReaderTab, viewportToNormalized, normalizedToViewport } from '../src/reader/state'
beforeEach(clearReaderTabs)
describe('reader session and page navigation', () => {
  it('reorders existing tab objects without losing their reading state', () => {
    const a = openReaderTab('a'), b = openReaderTab('b'), c = openReaderTab('c')
    b.page = 5; b.mode = 'spread'; b.scrollTop = 123
    moveReaderTab('a', null); expect(readerTabs.map(tab => tab.id)).toEqual(['b','c','a'])
    moveReaderTab('a', 'b'); expect(readerTabs).toEqual([a,b,c])
    expect(readerTabs[1]).toBe(b); expect(b).toMatchObject({ page: 5, mode: 'spread', scrollTop: 123 })
    moveReaderTab('a', 'a'); moveReaderTab('missing', null); moveReaderTab('a', 'missing')
    expect(readerTabs).toEqual([a,b,c])
  })
  it('deduplicates and retains only independent lightweight tab state', () => {
    const a = openReaderTab('a'); a.page = 4; a.mode = 'spread'
    openReaderTab('b').page = 2
    expect(openReaderTab('a')).toBe(a)
    expect(readerTabs).toHaveLength(2)
    expect(readerTabs[0]!.page).toBe(4)
    expect(readerTabs[1]!.page).toBe(2)
    clearReaderTabs(); expect(readerTabs).toHaveLength(0)
  })
  it('groups 1/2 first, retains last odd page and clamps group steps', () => {
    expect(pageGroup(4,7,'spread')).toEqual([3,4])
    expect(adjacentPage(4,7,'spread',1)).toBe(5)
    expect(adjacentPage(2,7,'spread',-1)).toBe(1)
    expect(pageGroup(7,7,'spread')).toEqual([7])
    expect(pageGroup(1,1,'spread')).toEqual([1])
    expect(pageGroup(4,7,'single')).toEqual([4])
  })
})
describe('viewport coordinate adapter with crop, rotation and UserUnit', () => {
  for (const rotation of [0,90,180,270]) for (const scale of [.5,1,2]) {
    it(`round trips cropped/user-unit page at rotation ${rotation}, scale ${scale}`, () => {
      const factor=scale*2, width=600*factor, height=800*factor
      const viewport = {
        viewBox:[20,30,620,830], width, height,
        convertToViewportPoint(x:number,y:number) {
          const u=(x-20)*factor,v=(830-y)*factor
          if(rotation===90)return [height-v,u]
          if(rotation===180)return [width-u,height-v]
          if(rotation===270)return [v,width-u]
          return [u,v]
        },
        convertToPdfPoint(x:number,y:number) {
          let u=x,v=y
          if(rotation===90){u=y;v=height-x}
          if(rotation===180){u=width-x;v=height-y}
          if(rotation===270){u=width-y;v=x}
          return [20+u/factor,830-v/factor]
        },
      }
      for (const point of [{x:0,y:0},{x:.25,y:.8},{x:1,y:1}]) {
        const screen = normalizedToViewport(viewport,point.x,point.y)
        const restored = viewportToNormalized(viewport,screen[0]!,screen[1]!)
        expect(restored.x).toBeCloseTo(point.x,10); expect(restored.y).toBeCloseTo(point.y,10)
      }
    })
  }
})
