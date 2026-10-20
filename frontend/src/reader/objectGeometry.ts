import { shallowRef } from 'vue'
import type { CoordinateViewport } from './state'
import type { PDFDocumentProxy } from 'pdfjs-dist'
import type { Geometry } from './annotations'
import type { NormalizedRect } from './context'
import { resizeBox, type BoxHandle } from './boxGeometry'
export const drawingTypes = ['ink','rectangle','circle','ellipse','signature','watermark','image']
export function bounds(g: Geometry): NormalizedRect {
  if(g.kind==='box') return g.rect
  if(g.kind==='points') {
    const xs=g.points.map(p=>p.x),ys=g.points.map(p=>p.y),x=Math.min(...xs),y=Math.min(...ys)
    return {x,y,width:Math.max(.00001,Math.max(...xs)-x),height:Math.max(.00001,Math.max(...ys)-y)}
  }
  if(g.kind==='anchor') return {x:g.x,y:g.y,width:.001,height:.001}
  return g.positions[0]!.rects[0]!
}
export function transformGeometry(g: Geometry,r: NormalizedRect): Geometry {
  if(g.kind==='box') return {...g,rect:r}
  if(g.kind==='points') { const old=bounds(g); return {...g,points:g.points.map(p=>({x:Math.max(0,Math.min(1,r.x+(p.x-old.x)/old.width*r.width)),y:Math.max(0,Math.min(1,r.y+(p.y-old.y)/old.height*r.height))}))} }
  return g
}
// ratio is normalized width/height, including the actual PDF page aspect.
export function resizeObject(r: NormalizedRect,dx: number,dy: number,handle: BoxHandle,ratio?:number): NormalizedRect {
  if(!ratio) return resizeBox(r,dx,dy,handle)
  const west=handle.includes('w'),north=handle.includes('n')
  const anchorX=west?r.x+r.width:r.x,anchorY=north?r.y+r.height:r.y
  let width=Math.max(.005, Math.abs(dx)>Math.abs(dy*ratio) ? r.width+(west?-dx:dx) : (r.height+(north?-dy:dy))*ratio)
  width=Math.min(width, (west?anchorX:1-anchorX), (north?anchorY:1-anchorY)*ratio)
  const height=width/ratio
  return {x:west?anchorX-width:anchorX,y:north?anchorY-height:anchorY,width,height}
}
export function dragRect(a:{x:number;y:number},b:{x:number;y:number},ratio?:number):NormalizedRect {
  let w=Math.abs(b.x-a.x),h=Math.abs(b.y-a.y)
  if(ratio) {w=Math.min(w,h*ratio);h=w/ratio}
  return {x:b.x<a.x?a.x-w:a.x,y:b.y<a.y?a.y-h:a.y,width:w,height:h}
}

export const liveInk=shallowRef<{documentId:string;segments:Extract<Geometry,{kind:'points'}>[]} | null>(null)
export const drawingViewports=new WeakMap<PDFDocumentProxy,Map<number,CoordinateViewport>>()

// Rotate in physical page space, then convert back to normalized coordinates.
export function rotateBoxPoint(p:{x:number;y:number},r:NormalizedRect,angle:number,pageRatio:number){
  const cx=r.x+r.width/2,cy=r.y+r.height/2,theta=angle*Math.PI/180,c=Math.cos(theta),s=Math.sin(theta)
  return {x:cx+c*(p.x-cx)-s*(p.y-cy)/pageRatio,y:cy+s*(p.x-cx)*pageRatio+c*(p.y-cy)}
}
export function resizeRotatedObject(r:NormalizedRect,dx:number,dy:number,handle:BoxHandle,angle:number,pageRatio:number){
  const theta=angle*Math.PI/180,c=Math.cos(theta),s=Math.sin(theta)
  const next=resizeObject(r,c*dx+s*dy/pageRatio,-s*dx*pageRatio+c*dy,handle,r.width/r.height)
  const center=rotateBoxPoint({x:next.x+next.width/2,y:next.y+next.height/2},r,angle,pageRatio)
  return {...next,x:Math.max(0,Math.min(1-next.width,center.x-next.width/2)),y:Math.max(0,Math.min(1-next.height,center.y-next.height/2))}
}
