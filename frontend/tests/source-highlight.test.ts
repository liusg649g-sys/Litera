import { expect, it } from 'vitest'
import { reliableSourcePosition, validateSourceTextRanges } from '../src/reader/sourceHighlight'
import type { SelectionPosition } from '../src/reader/context'

const position=(overrides:Partial<SelectionPosition>={}):SelectionPosition=>({
  pageNumber:2,
  textQuote:'Optical microscopy',
  rects:[{x:.1,y:.2,width:.3,height:.04}],
  textRanges:[{item:3,start:0,end:7},{item:4,start:0,end:11}],
  ...overrides,
})

it('accepts only structurally reliable saved geometry for the requested physical page',()=>{
  expect(reliableSourcePosition([position()],2)).toEqual(position())
  expect(reliableSourcePosition([position()],1)).toBeNull()
  expect(reliableSourcePosition([position({textRanges:undefined})],2)).toBeNull()
  expect(reliableSourcePosition([position({rects:[{x:.9,y:0,width:.2,height:.1}]})],2)).toBeNull()
  expect(reliableSourcePosition([position({textRanges:[{item:4,start:0,end:2},{item:3,start:0,end:2}]})],2)).toBeNull()
})

it('strictly reconstructs a single-line selection from saved PDF.js item ranges',()=>{
  const result=validateSourceTextRanges(position(),['','','','Optical',' microscopy'],[false,false,false,false,false])
  expect(result).toMatchObject({ok:true,parts:[{item:3,start:0,end:7},{item:4,start:0,end:11}]})
})

it('preserves PDF.js line breaks while validating a multi-line selection',()=>{
  const selected=position({textQuote:'first line\nsecond line',textRanges:[{item:1,start:0,end:10},{item:2,start:0,end:11}]})
  expect(validateSourceTextRanges(selected,['','first line','second line'],[false,true,false])).toMatchObject({ok:true})
})

it('falls back when a range is invalid or current text no longer matches exactly',()=>{
  expect(validateSourceTextRanges(position(),['','','','Optical',' microscXpy'],[])).toMatchObject({ok:false,reason:expect.stringContaining('逐字复核')})
  expect(validateSourceTextRanges(position(),['','','','Optical',' micro'],[])).toMatchObject({ok:false,reason:expect.stringContaining('字符范围')})
})
