import type { NormalizedRect } from './context'
import { mergeTextRects } from './context'

// Display-only line layout: keep saved character geometry intact, including
// legacy separate citation rectangles. Raised small text belongs to the body
// line below it, never to the preceding line whose baseline is above it.
export function textMarkLines(rects: NormalizedRect[], width: number, height: number) {
  const rows = mergeTextRects(rects,width,height).map(rect => ({ rect:{...rect}, body:{...rect}, attached:false }))
  for (const small of [...rows].sort((a,b)=>a.body.height-b.body.height)) {
    const s=small.body, sh=s.height*height, sb=(s.y+s.height*(s.baseline??.8))*height
    const candidates=rows.filter(row=>row!==small && !row.attached).map(row=> {
      const b=row.body, bh=b.height*height, baseline=(b.y+b.height*(b.baseline??.8))*height
      const gap=Math.max(0,(Math.max(s.x,b.x)-Math.min(s.x+s.width,b.x+b.width))*width)
      return {row,bh,gap,rise:(sb-baseline)/bh}
    }).filter(c=>sh/c.bh>=.3 && sh/c.bh<=.85 && s.width*width<=6*c.bh && c.gap<=.65*c.bh && c.rise>=-.95 && c.rise<=-.12)
    candidates.sort((a,b)=>a.gap/a.bh-b.gap/b.bh || Math.abs(a.rise)-Math.abs(b.rise))
    const target=candidates[0]?.row
    if (!target) continue
    const a=target.rect, r=small.rect, x=Math.min(a.x,r.x), y=Math.min(a.y,r.y)
    target.rect={x,y,width:Math.max(a.x+a.width,r.x+r.width)-x,height:Math.max(a.y+a.height,r.y+r.height)-y}
    small.attached=true
  }
  const lines: {rect:NormalizedRect;body:NormalizedRect}[]=[]
  for (const row of rows.filter(row=>!row.attached).sort((a,b)=>a.body.y-b.body.y || a.rect.x-b.rect.x)) {
    const line=lines.find(p=> {
      const h=Math.min(p.body.height,row.body.height)*height
      const baseline=(r:NormalizedRect)=>(r.y+r.height*(r.baseline??.8))*height
      const gap=(Math.max(p.rect.x,row.rect.x)-Math.min(p.rect.x+p.rect.width,row.rect.x+row.rect.width))*width
      return Math.abs(baseline(p.body)-baseline(row.body))<=h*.12 && Math.max(p.body.height,row.body.height)<=Math.min(p.body.height,row.body.height)*1.4 && gap<=h*.55
    })
    if (!line) { lines.push({rect:row.rect,body:row.body}); continue }
    const a=line.rect,b=row.rect,x=Math.min(a.x,b.x),y=Math.min(a.y,b.y)
    line.rect={x,y,width:Math.max(a.x+a.width,b.x+b.width)-x,height:Math.max(a.y+a.height,b.y+b.height)-y}
    if(row.body.height>line.body.height)line.body=row.body
  }
  return lines
}

// DOM Range boxes include font descent. Keep strokes inside that line box so
// compact leading cannot push underline/waves into the following line.
export function textStroke(rect: NormalizedRect, pageHeight: number, width: number, middle = false) {
  const height = rect.height * pageHeight
  const thickness = Math.min(width, height * .065)
  const baseline = rect.baseline ?? .8
  const offset = middle ? Math.max(.35,Math.min(.6,baseline-.32)) : Math.max(.82,Math.min(.9,baseline+.075))
  return { y: rect.y + rect.height * offset, thickness, amplitude: height * .035 }
}

export function smoothWave(a: number[], b: number[], amplitude: number, wavelength: number) {
  const dx=b[0]!-a[0]!, dy=b[1]!-a[1]!, length=Math.hypot(dx,dy)
  if (!length) return ''
  const halves=Math.max(2,Math.ceil(length/(wavelength/2))), step=length/halves
  const point=(t:number,n:number) => `${a[0]!+dx/length*t-dy/length*n} ${a[1]!+dy/length*t+dx/length*n}`
  let path=`M ${point(0,0)}`
  // Quadratic arches meet with matching tangents, including fractional endpoints.
  for(let i=0;i<halves;i++) path+=` Q ${point((i+.5)*step,(i%2 ? -1 : 1)*amplitude*2)} ${point((i+1)*step,0)}`
  return path
}
