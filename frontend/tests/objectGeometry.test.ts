import {describe,it,expect} from 'vitest'
import {dragRect,resizeObject,transformGeometry,bounds,rotateBoxPoint,resizeRotatedObject} from '../src/reader/objectGeometry'
describe('B2 physical object geometry',()=>{
  it('creates circles in all drag directions on different page sizes',()=>{
    for(const [w,h] of [[612,792],[700,792],[580,740],[200,300]])for(const dx of [-.2,.2])for(const dy of [-.3,.3]){
      const r=dragRect({x:.5,y:.5},{x:.5+dx,y:.5+dy},h!/w!)
      expect(r.width*w!/(r.height*h!)).toBeCloseTo(1,10);expect(r.x).toBeGreaterThanOrEqual(0);expect(r.y).toBeGreaterThanOrEqual(0)
    }
  })
  it('resizes corner handles at boundaries while retaining aspect and opposite corner',()=>{
    const r={x:.2,y:.3,width:.3,height:.2}
    for(const handle of ['nw','ne','se','sw'] as const)for(const delta of [-2,-.05,.05,2]){
      const next=resizeObject(r,delta,delta,handle,1.5)
      expect(next.width/next.height).toBeCloseTo(1.5,9)
      expect(next.x).toBeGreaterThanOrEqual(0);expect(next.y).toBeGreaterThanOrEqual(0);expect(next.x+next.width).toBeLessThanOrEqual(1.00000001);expect(next.y+next.height).toBeLessThanOrEqual(1.00000001)
      expect(handle.includes('w')?next.x+next.width:next.x).toBeCloseTo(handle.includes('w')?.5:.2,10)
    }
  })
  it('allows independent ellipse resizing and transforms an entire ink path',()=>{
    const r={x:.2,y:.3,width:.3,height:.2};expect(resizeObject(r,.1,0,'e').height).toBe(r.height)
    const ink={kind:'points' as const,pageNumber:1,points:[{x:.1,y:.2},{x:.2,y:.3},{x:.4,y:.5}]}
    const moved=transformGeometry(ink,{x:.2,y:.3,width:.6,height:.3})
    expect(bounds(moved)).toEqual({x:.2,y:.3,width:.6000000000000001,height:.3});expect(ink.points[0]).toEqual({x:.1,y:.2})
  })
})


describe('inserted object rotation in physical page space',()=>{
  it('rotates by physical degrees on rectangular pages and round trips',()=>{
    const r={x:.3,y:.3,width:.2,height:.1},p={x:.5,y:.35}
    for(const ratio of [612/792,580/740,2])for(const angle of [-90,-37,0,31,90]){
      const q=rotateBoxPoint(p,r,angle,ratio),back=rotateBoxPoint(q,r,-angle,ratio)
      expect(back.x).toBeCloseTo(p.x,10);expect(back.y).toBeCloseTo(p.y,10)
      expect(Math.hypot((q.x-.4)*ratio,q.y-.35)).toBeCloseTo(.1*ratio,10)
    }
  })
  it('resizes a rotated image while keeping its opposite visual corner and aspect',()=>{
    const r={x:.3,y:.3,width:.2,height:.1}
    for(const handle of ['nw','ne','se','sw'] as const)for(const angle of [-90,-37,0,31,90])for(const ratio of [612/792,2]){
      const corner=(box:typeof r)=>({x:handle.includes('w')?box.x+box.width:box.x,y:handle.includes('n')?box.y+box.height:box.y})
      const before=rotateBoxPoint(corner(r),r,angle,ratio),next=resizeRotatedObject(r,.01,.02,handle,angle,ratio),after=rotateBoxPoint(corner(next),next,angle,ratio)
      expect(next.width/next.height).toBeCloseTo(2,10)
      expect(after.x).toBeCloseTo(before.x,10);expect(after.y).toBeCloseTo(before.y,10)
    }
  })
})
