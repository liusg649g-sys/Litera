import {describe,it,expect,vi} from 'vitest'
import {textHasUnmappedCharacters,pageTextMapping,unreliableTextMessage} from '../src/reader/textQuality'
import {createTranslation} from '../src/reader/translation'
import type {PDFPageProxy} from 'pdfjs-dist'
describe('PDF text reliability (no character repair)',()=>{
 it('keeps normal English Chinese Greek math punctuation and whitespace untouched',()=>{const text='English 中文 αβ ≤ ± — ﬁ\nNext\tline';expect(textHasUnmappedCharacters(text)).toBe(false)})
 it.each(['a\u0003b','a\u001fb','\uFFFD','\uE001','\uD800'])('rejects unportable characters %j',text=>expect(textHasUnmappedCharacters(text)).toBe(true))
 it('marks only the affected font including printable fragments and caches per page',async()=>{const getTextContent=vi.fn().mockResolvedValue({items:[{str:'\u0003\u000f123',fontName:'bad'},{str:'Normal English',fontName:'good'}]});const page={getTextContent} as unknown as PDFPageProxy;const mapping=await pageTextMapping(page);expect(mapping.fonts.has('bad')).toBe(true);expect(mapping.fonts.has('good')).toBe(false);await pageTextMapping(page);expect(getTextContent).toHaveBeenCalledOnce()})
 it('never sends an unreliable mapping even when chosen fragment is printable',async()=>{const send=vi.fn();const m=createTranslation(send);m.context({documentId:'doc',pageNumber:5,contextRevision:1,annotationId:null,selectedText:'123',selectionPosition:[{pageNumber:5,rects:[{x:.1,y:.1,width:.1,height:.1}],textQuote:'123'}],textExtractionIssue:unreliableTextMessage});await m.request();expect(send).not.toHaveBeenCalled();expect(m.state.source?.text).toBe('123');expect(m.state.error).toBe(unreliableTextMessage);m.dispose()})
})

it('an identical printable selection gains its new reliability warning',async()=>{const send=vi.fn();const m=createTranslation(send);const context={documentId:'doc',pageNumber:5,contextRevision:1,annotationId:null,selectedText:'123',selectionPosition:[{pageNumber:5,rects:[{x:.1,y:.1,width:.1,height:.1}],textQuote:'123'}]};m.context(context);expect(m.state.source?.textExtractionIssue).toBeUndefined();m.context({...context,contextRevision:2,textExtractionIssue:unreliableTextMessage});await m.request();expect(m.state.source?.textExtractionIssue).toBe(unreliableTextMessage);expect(send).not.toHaveBeenCalled();m.dispose()})
