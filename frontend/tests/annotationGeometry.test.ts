import { describe, expect, it } from 'vitest'
import { mergeTextRects } from '../src/reader/context'
import { smoothWave, textStroke, textMarkLines } from '../src/reader/annotationGeometry'

describe('shared text annotation geometry', () => {
  it('joins split words and normal whitespace without crossing columns or compact lines', () => {
    const rects = [
      { x:.1,y:.2,width:.04,height:.015 }, { x:.145,y:.2,width:.05,height:.015 },
      { x:.1,y:.22,width:.09,height:.015 }, { x:.5,y:.2,width:.08,height:.015 },
    ]
    const merged=mergeTextRects(rects,600,800)
    expect(merged).toHaveLength(3)
    expect(merged[0]).toMatchObject({x:.1,y:.2})
    expect(merged[0]!.width).toBeCloseTo(.095)
    expect(rects[0]!.width).toBe(.04)
    expect(mergeTextRects(rects,1200,1600)).toEqual(merged)
  })
  it('keeps raw superscript anchors separate and does not bridge columns or unselected lines', () => {
    expect(mergeTextRects([{x:.1,y:.2,width:.1,height:.02},{x:.21,y:.19,width:.01,height:.01}],600,800)).toHaveLength(2)
    expect(mergeTextRects([{x:.1,y:.2,width:.1,height:.02},{x:.3,y:.2,width:.1,height:.02}],600,800)).toHaveLength(2)
  })
  it('keeps even very thick requested strokes and smooth waves inside a compact line', () => {
    const r={x:.1,y:.2,width:.4,height:.012}, s=textStroke(r,800,20)
    expect(s.thickness).toBeLessThan(1)
    expect((s.y-r.y)*800+s.amplitude+s.thickness/2).toBeLessThan(r.height*800)
    expect(textStroke(r,800,1,true).y).toBeLessThan(s.y)
    const path=smoothWave([0,0],[100,0],.4,4)
    expect(path).toContain(' Q '); expect(path).not.toContain(' L ')
    expect(path).not.toContain('NaN'); expect(path.endsWith('100 0')).toBe(true)
    expect(smoothWave([0,0],[0,100],.4,4)).not.toContain('NaN')
  })
  it('aligns raised citations with the body, including middle-of-line references, without changing saved rectangles', () => {
    const body={x:.1,y:.2,width:.1,height:.02,baseline:.8}
    const citation={x:.205,y:.194,width:.015,height:.012,baseline:.8}
    const continuation={x:.225,y:.2,width:.1,height:.02,baseline:.8}
    const source=[body,citation,continuation], before=JSON.stringify(source)
    const lines=textMarkLines(source,600,800)
    expect(lines).toHaveLength(1)
    expect(lines[0]!.rect.y).toBe(.194)
    expect(lines[0]!.rect.width).toBeCloseTo(.225)
    expect(textStroke(lines[0]!.body,800,1)).toEqual(textStroke(body,800,1))
    expect(textStroke(lines[0]!.body,800,1,true)).toEqual(textStroke(body,800,1,true))
    expect(JSON.stringify(source)).toBe(before)
    expect(textMarkLines(source,1200,1600)).toEqual(lines)
  })
  it('does not attach raised text to the previous compact line, next line or another column', () => {
    const body={x:.1,y:.2,width:.1,height:.02}
    const citation={x:.205,y:.194,width:.015,height:.012}
    const previous={x:.1,y:.178,width:.4,height:.02}, next={x:.1,y:.224,width:.4,height:.02}
    expect(textMarkLines([previous,body,citation,next],600,800)).toHaveLength(3)
    expect(textMarkLines([body,{...citation,x:.5}],600,800)).toHaveLength(2)
    expect(textMarkLines([citation],600,800)).toEqual([{rect:citation,body:citation}])
  })
})
