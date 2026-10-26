import { describe, expect, it, vi, afterEach } from 'vitest'
import { noteCaptureApi, captureDraftIssue, storedSourceBlock, translationMatchesSelection, type CaptureRequest, type NoteCaptureDraft, type CaptureSource } from '../src/notes/captures'
import type { ReaderContext } from '../src/reader/context'
import type { TranslationResult } from '../src/reader/translation'
import { api } from '../src/api'
vi.mock('../src/api',async original=>({...await original<typeof import('../src/api')>(),api:vi.fn()}))
afterEach(()=>vi.mocked(api).mockReset())
const position={pageNumber:3,textQuote:'Optical microscopy',rects:[{x:.1,y:.2,width:.2,height:.03}]}
const context:ReaderContext={documentId:'doc-a',pageNumber:3,selectedText:position.textQuote,selectionPosition:[position],contextRevision:8,annotationId:null}
const result:TranslationResult={originalText:position.textQuote,translatedText:'隔离 Mock 译文',source:{documentId:'doc-a',pageNumber:3,contextRevision:7,sourceLanguage:'en',targetLanguage:'zh',sourceType:'translation'}}
const draft=():NoteCaptureDraft<CaptureSource>=>({title:'Document A',source:{kind:'pdf_excerpt',documentId:'doc-a',pageNumber:3,originalText:position.textQuote,positions:[position],contextRevision:8,historical:false,confirmHistorical:false}})
describe('note capture source guards without a database/model',()=>{
 it('requires the actual matching PDF selection, position, document and direction',()=>{
   expect(translationMatchesSelection(result,[position],context,'en-zh')).toBe(true)
   expect(translationMatchesSelection(result,[position],null,'en-zh')).toBe(false)
   expect(translationMatchesSelection(result,[position],{...context,selectedText:'',selectionPosition:null},'en-zh')).toBe(false)
   expect(translationMatchesSelection(result,[position],{...context,documentId:'doc-b'},'en-zh')).toBe(false)
   expect(translationMatchesSelection(result,[position],context,'zh-en')).toBe(false)
   expect(translationMatchesSelection(result,[],context,'en-zh')).toBe(false)
   expect(translationMatchesSelection(result,[position],{...context,textExtractionIssue:'Invalid mapping'},'en-zh')).toBe(false)
 })
 it('rejects unreliable text and translation without a signed proof',()=>{
   expect(captureDraftIssue(draft())).toBe('')
   const bad=draft();bad.source.originalText='private\uE001';expect(captureDraftIssue(bad)).toContain('无法可靠提取')
   const translation=draft();translation.source.kind='translation_excerpt';translation.source.translatedText='Mock translation';expect(captureDraftIssue(translation)).toContain('凭证')
   translation.source.translationProof={version:1,issuedAt:100,signature:'a'.repeat(64),provenance:'isolated_mock'};expect(captureDraftIssue(translation)).toBe('')
 })
 it('recognizes supported blocks and leaves unknown schemas uninterpreted',()=>{
   expect(storedSourceBlock({id:'s',kind:'unknown',originalText:'word',source:{documentId:'d',title:'title',pageNumber:1}})).toBeNull()
   expect(storedSourceBlock({id:'s',kind:'pdf_excerpt',originalText:'word',source:{documentId:'d',title:'title',pageNumber:1}})?.id).toBe('s')
   expect(storedSourceBlock({id:'s',kind:'translation_excerpt',originalText:'word',source:{documentId:'d',title:'title',pageNumber:1}})).toBeNull()
 })
 it('uses title-only personal pagination and sends stable operation payload to capture endpoint',async()=>{
   await noteCaptureApi.list(' two words ',2)
   expect(api).toHaveBeenCalledWith('/notes?page=2&pageSize=20&title=two+words')
   const request:CaptureRequest={operationId:'op-1',noteId:'note-1',version:null,newNoteTitle:'Excerpt',associationMode:'link',source:draft().source}
   await noteCaptureApi.save(request)
   expect(api).toHaveBeenLastCalledWith('/notes/captures',{method:'POST',body:JSON.stringify(request)},expect.any(String))
 })
})
