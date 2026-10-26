import { api } from '../api'
import { auth } from '../auth'
import type { NoteDTO, NotesPage } from '../notes'
import type { ReaderContext, SelectionPosition } from '../reader/context'
import type { TranslationResult } from '../reader/translation'
import { textHasUnmappedCharacters } from '../reader/textQuality'

export interface TranslationProof { version: 1; issuedAt: number; signature: string; provenance: 'model_api'|'isolated_mock' }
export interface CaptureSource {
  kind: 'pdf_excerpt'|'translation_excerpt'
  documentId: string; pageNumber: number; originalText: string
  positions: SelectionPosition[]; contextRevision: number
  translatedText?: string; sourceLanguage?: string; targetLanguage?: string
  translationProof?: TranslationProof; modelInputText?: string; normalizationCount?: number
  historical: boolean; confirmHistorical: boolean
}
export interface AiAnswerSource {
  kind:'ai_answer'; answerId:string; answerRevision:number
  historical:boolean; confirmHistorical:boolean; confirmUncited:boolean
}
export interface AnswerCitation {
  citationId:string; documentId:string; title:string; fileSha256:string
  extractionVersion:string; chunkId:string; pageNumber:number; quote:string
}
export interface AnswerSnapshot {
  answerId:string; answerRevision:number; question:string; answer:string
  mode:'question'|'summary'|'analysis'; status:'answered'|'insufficient_evidence'
  provenance:'model_api'|'isolated_mock'; evidenceState:'verified'|'none'
  contextDocument:{documentId:string;title:string;fileSha256:string;contextRevision:number;extractionVersion:string|null}
  citations:AnswerCitation[]
}
export interface StoredAiAnswerBlock {
  id:string; kind:'ai_answer'; blockSchemaVersion:1; createdAt:string
  question:string; answer:string; answerRef:Pick<AnswerSnapshot,'answerId'|'answerRevision'|'mode'|'status'|'provenance'>
  contextDocument:AnswerSnapshot['contextDocument']; evidenceState:'verified'|'none';citations:AnswerCitation[]
  historical:boolean;uncitedAcknowledged:boolean;requestFingerprint:string
}
export type NoteCaptureSource=CaptureSource|AiAnswerSource
export interface NoteCaptureDraft<T extends NoteCaptureSource=NoteCaptureSource> { source: T; title: string; answerPreview?:AnswerSnapshot }
export interface NoteSourceLocation {id:string;source:{documentId:string;title:string;fileSha256:string;pageNumber:number;positions:SelectionPosition[]}}
export const captureDocumentId=(draft:NoteCaptureDraft|null)=>!draft?'':draft.source.kind==='ai_answer'?draft.answerPreview?.contextDocument.documentId || '':draft.source.documentId
export function storedAiAnswer(value:unknown):StoredAiAnswerBlock|null {
  if(!value || typeof value!=='object')return null
  const b=value as Partial<StoredAiAnswerBlock>
  if(b.kind!=='ai_answer' || b.blockSchemaVersion!==1 || typeof b.id!=='string' || typeof b.question!=='string' || typeof b.answer!=='string' || !b.answerRef || !b.contextDocument || !Array.isArray(b.citations) || !['verified','none'].includes(b.evidenceState || ''))return null
  if(typeof b.answerRef.answerId!=='string' || !Number.isInteger(b.answerRef.answerRevision) || !['model_api','isolated_mock'].includes(b.answerRef.provenance) || typeof b.contextDocument.documentId!=='string' || !/^[a-f0-9]{64}$/i.test(b.contextDocument.fileSha256 || ''))return null
  if(b.evidenceState==='none'?b.citations.length!==0:b.citations.length===0)return null
  if(b.citations.some(c=>!c || typeof c.quote!=='string' || !c.quote.trim() || typeof c.documentId!=='string' || typeof c.title!=='string' || !Number.isInteger(c.pageNumber) || c.pageNumber<1 || !/^[a-f0-9]{64}$/i.test(c.fileSha256 || '')))return null
  return b as StoredAiAnswerBlock
}
export interface CaptureRequest {
  operationId: string; noteId: string; version: number|null; newNoteTitle: string|null
  associationMode: 'link'|'keep'; source: NoteCaptureSource
}
export interface CaptureResponse { note: NoteDTO; blockId: string; created: boolean; linked: boolean; replayed: boolean; deduplicated?:boolean }
export interface CaptureConfig { available: boolean; formatVersion: 1; maxOriginalLength: number; maxTranslatedLength: number; maxBlocks: number; maxSourceBytes: number; supportedSourceKinds?:string[]; aiAnswerCapture?:{available:boolean;isolatedMock:boolean} }
export interface StoredSourceBlock {
  id: string; kind: 'pdf_excerpt'|'translation_excerpt'; createdAt: string
  originalText: string; translatedText?: string; sourceLanguage?: string; targetLanguage?: string
  modelInputText?: string; normalizationCount?: number
  source: { documentId: string; title: string; fileSha256: string; pageNumber: number; pageNumbers: number[]; positions: SelectionPosition[]; contextRevision: number; precision: 'page' }
  translationProvenance?: 'model_api'|'isolated_mock'; historical: boolean; requestFingerprint: string
}
export const noteCaptureApi = {
  answerPreview: (id:string,revision:number)=>api<AnswerSnapshot>('/notes/answer-preview/'+encodeURIComponent(id)+'?revision='+revision),
  config: () => api<CaptureConfig>('/notes/capture-config'),
  list: (title = '', page = 1) => {
    const params = new URLSearchParams({page: String(page), pageSize: '20'})
    if (title.trim()) params.set('title', title.trim())
    return api<NotesPage>('/notes?' + params)
  },
  get: (id: string) => api<NoteDTO>('/notes/' + encodeURIComponent(id)),
  save: (request: CaptureRequest) => api<CaptureResponse>('/notes/captures', {method:'POST',body:JSON.stringify(request)}, auth.csrfToken),
}

// Retained translation state alone is not a current PDF selection. Inputs use the
// actual reader snapshot so focus/tab changes cannot relabel a previous result.
export function translationMatchesSelection(result: TranslationResult|null, positions: readonly SelectionPosition[], context: Readonly<ReaderContext>|null, direction: string): boolean {
  if (!result || !context?.selectedText.trim() || !context.selectionPosition?.length || context.textExtractionIssue || textHasUnmappedCharacters(context.selectedText)) return false
  const [from, to] = direction.split('-')
  return result.source.documentId === context.documentId && result.source.pageNumber === context.selectionPosition[0]!.pageNumber && result.originalText === context.selectedText && result.source.sourceLanguage === from && result.source.targetLanguage === to && JSON.stringify(positions) === JSON.stringify(context.selectionPosition)
}
export function captureDraftIssue(draft: NoteCaptureDraft, config?: CaptureConfig|null): string {
  const source=draft.source
  if(source.kind==='ai_answer'){
    if(!config?.aiAnswerCapture?.available)return 'AI回答来源服务尚未接入。'
    const preview=draft.answerPreview
    if(!preview || preview.answerId!==source.answerId || preview.answerRevision!==source.answerRevision)return '正在核验AI回答来源，请稍候。'
    if(!preview.answer.trim() || !preview.contextDocument.documentId)return '回答来源信息不完整。'
    return ''
  }
  if (!source.originalText.trim() || textHasUnmappedCharacters(source.originalText)) return '无法可靠提取原文，不能保存此摘录。请重新选择具有有效文字映射的 PDF 正文。'
  if (source.originalText.length > (config?.maxOriginalLength ?? 6000)) return '原文过长，请缩小 PDF 选区后重试。'
  if (!source.documentId || !Number.isInteger(source.pageNumber) || source.pageNumber < 1) return '来源信息不完整，请重新选择 PDF 正文。'
  if (source.kind === 'translation_excerpt') {
    if (!source.translatedText?.trim()) return '尚无可保存的译文。'
    if (source.translatedText.length > (config?.maxTranslatedLength ?? 20000)) return '译文过长，不能保存此摘录。'
    if (!source.translationProof || source.translationProof.version !== 1 || !['model_api','isolated_mock'].includes(source.translationProof.provenance)) return '此译文缺少可验证的来源凭证，请重新翻译后保存。'
  }
  return ''
}

export function storedSourceBlock(value: unknown): StoredSourceBlock|null {
  if (!value || typeof value !== 'object') return null
  const block=value as Partial<StoredSourceBlock>, source=block.source
  if (typeof block.id !== 'string' || !['pdf_excerpt','translation_excerpt'].includes(block.kind ?? '') || typeof block.originalText !== 'string' || !source || typeof source.documentId !== 'string' || typeof source.title !== 'string' || !Number.isInteger(source.pageNumber) || source.pageNumber < 1 || (block.kind === 'translation_excerpt' && typeof block.translatedText !== 'string')) return null
  return block as StoredSourceBlock
}
