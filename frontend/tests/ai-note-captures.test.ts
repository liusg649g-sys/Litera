import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {flushPromises,mount,type VueWrapper} from '@vue/test-utils'
import SaveToNoteDialog from '../src/components/SaveToNoteDialog.vue'
import AiAnswerNoteBlock from '../src/components/AiAnswerNoteBlock.vue'
import NoteSourceBlocks from '../src/components/NoteSourceBlocks.vue'
import {ApiError} from '../src/api'
import {noteCaptureApi,storedAiAnswer,type AnswerSnapshot,type NoteCaptureDraft,type StoredAiAnswerBlock} from '../src/notes/captures'
import type {NoteDTO} from '../src/notes'
let wrapper:VueWrapper|undefined
const snapshot=():AnswerSnapshot=>({answerId:'answer-a',answerRevision:1,question:'[MOCK] Test question',answer:'[MOCK] Synthetic answer',mode:'question',status:'answered',provenance:'isolated_mock',evidenceState:'verified',contextDocument:{documentId:'doc-a',title:'Synthetic PDF',fileSha256:'a'.repeat(64),contextRevision:2,extractionVersion:'mock-v1'},citations:[{citationId:'MOCK-1',documentId:'doc-a',title:'Synthetic PDF',fileSha256:'a'.repeat(64),extractionVersion:'mock-v1',chunkId:'MOCK-CHUNK-1',pageNumber:3,quote:'Synthetic quote'}]})
const note=():NoteDTO=>({id:'note-a',title:'Current note',content:'Draft',version:4,documents:[{id:'doc-a',title:'Synthetic PDF'}],sources:[],contentFormat:'plain-text',sourceSchemaVersion:1,createdAt:'2026-10-26',updatedAt:'2026-10-26'})
const draft=():NoteCaptureDraft=>({title:'Untrusted title ignored',source:{kind:'ai_answer',answerId:'answer-a',answerRevision:1,historical:false,confirmHistorical:false,confirmUncited:false}})
const block=():StoredAiAnswerBlock=>({id:'block-a',kind:'ai_answer',blockSchemaVersion:1,createdAt:'2026-10-26',question:snapshot().question,answer:snapshot().answer,answerRef:{answerId:'answer-a',answerRevision:1,mode:'question',status:'answered',provenance:'isolated_mock'},contextDocument:snapshot().contextDocument,citations:snapshot().citations,evidenceState:'verified',historical:false,uncitedAcknowledged:false,requestFingerprint:'digest'})
async function open(preferred:NoteDTO|null=null,d=draft()){wrapper=mount(SaveToNoteDialog,{props:{draft:d,preferredNote:preferred,ownerId:'owner-a'},attachTo:document.body});await flushPromises();return wrapper}
async function submit(){await wrapper!.get('form').trigger('submit');await flushPromises()}
beforeEach(()=>{
 vi.spyOn(noteCaptureApi,'config').mockResolvedValue({available:true,formatVersion:1,maxOriginalLength:6000,maxTranslatedLength:20000,maxBlocks:100,maxSourceBytes:1048576,aiAnswerCapture:{available:true,isolatedMock:true}})
 vi.spyOn(noteCaptureApi,'answerPreview').mockResolvedValue(snapshot())
 vi.spyOn(noteCaptureApi,'get').mockResolvedValue(note())
 vi.spyOn(noteCaptureApi,'list').mockResolvedValue({items:[note()],page:1,pageSize:20,total:1})
 vi.spyOn(noteCaptureApi,'save').mockResolvedValue({note:note(),blockId:'block-a',created:true,linked:true,replayed:false})
})
afterEach(()=>{wrapper?.unmount();wrapper=undefined;vi.restoreAllMocks()})
it('reads authoritative preview and saves only the answer reference to a new note',async()=>{
 await open();expect(noteCaptureApi.answerPreview).toHaveBeenCalledWith('answer-a',1)
 expect(wrapper!.text()).toContain('模拟问答数据');expect(wrapper!.text()).toContain('Synthetic answer');expect(noteCaptureApi.save).not.toHaveBeenCalled()
 await submit();const request=vi.mocked(noteCaptureApi.save).mock.calls[0]![0]
 expect(request.newNoteTitle).toBe('AI 回答笔记');expect(request.source).toEqual(draft().source)
 expect(request.source).not.toHaveProperty('answer');expect(request.source).not.toHaveProperty('citations');expect(request).not.toHaveProperty('content')
})
it('uses the latest current-note version and supports selecting another personal note',async()=>{
 await open({...note(),version:1});await submit()
 expect(noteCaptureApi.save).toHaveBeenLastCalledWith(expect.objectContaining({noteId:'note-a',version:4,newNoteTitle:null}))
 wrapper!.unmount();await open();await wrapper!.findAll('input[type=radio]').find(x=>x.element.parentElement?.textContent?.includes('其他已有'))!.setValue(true);await flushPromises()
 await wrapper!.get('[aria-label="选择笔记：Current note"]').trigger('click');await flushPromises();await submit()
 expect(noteCaptureApi.save).toHaveBeenLastCalledWith(expect.objectContaining({noteId:'note-a',version:4}))
})
it('requires explicit unverified acknowledgement, never invents a source page',async()=>{
 vi.mocked(noteCaptureApi.answerPreview).mockResolvedValue({...snapshot(),evidenceState:'none',citations:[],status:'insufficient_evidence'})
 await open();expect(wrapper!.text()).toContain('没有可信引用');expect(wrapper!.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
 await submit();expect(noteCaptureApi.save).not.toHaveBeenCalled()
 await wrapper!.get('input[type=checkbox]').setValue(true);await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0].source).toMatchObject({kind:'ai_answer',confirmUncited:true})
})
it('refuses to use an unverified fallback after a source-service error',async()=>{
 vi.mocked(noteCaptureApi.answerPreview).mockRejectedValue(new ApiError(422,'AI_EVIDENCE_INVALID','Citation cannot be verified'))
 await open(note());expect(wrapper!.text()).toContain('Citation cannot be verified');await submit();expect(noteCaptureApi.save).not.toHaveBeenCalled()
 expect(wrapper!.find('input[type=checkbox]').exists()).toBe(false)
})
it('retains an identical operation after a lost response and requires reload after CAS conflict',async()=>{
 vi.mocked(noteCaptureApi.save).mockRejectedValueOnce(new ApiError(503,'AI_ANSWER_UNAVAILABLE','Service unavailable'))
 await open(note());await submit();const first=vi.mocked(noteCaptureApi.save).mock.calls[0]![0]
 expect(wrapper!.text()).toContain('重试将核实同一操作');await submit();expect(vi.mocked(noteCaptureApi.save).mock.calls[1]![0]).toEqual(first)
 wrapper!.unmount();vi.mocked(noteCaptureApi.save).mockRejectedValueOnce(new ApiError(409,'NOTE_VERSION_CONFLICT','Conflict'));await open(note());await submit()
 expect(wrapper!.text()).toContain('重新读取目标笔记');expect(wrapper!.emitted('captured')).toBeUndefined()
})
it('ignores a late preview after the owner/dialog changes',async()=>{
 let resolve!:(v:AnswerSnapshot)=>void
 vi.mocked(noteCaptureApi.answerPreview).mockReturnValueOnce(new Promise(r=>resolve=r))
 const pending=open();await flushPromises();await wrapper!.setProps({draft:null,ownerId:'owner-b'});resolve(snapshot());await pending;await flushPromises()
 expect(wrapper!.find('dialog').exists()).toBe(false);expect(noteCaptureApi.save).not.toHaveBeenCalled()
})
it('requires historical confirmation separately from unverified acknowledgement',async()=>{
 const d=draft();d.source.historical=true;await open(null,d)
 expect(wrapper!.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
 await wrapper!.get('input[type=checkbox]').setValue(true);await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0].source).toMatchObject({historical:true,confirmHistorical:true})
})
it('renders generated content distinctly, safely, and navigates only verified citation pages',async()=>{
 const b=block();b.answer='<script>not executable</script>';expect(storedAiAnswer(b)?.id).toBe('block-a')
 wrapper=mount(AiAnswerNoteBlock,{props:{block:b}});expect(wrapper.find('script').exists()).toBe(false)
 await wrapper.get('button').trigger('click');expect(wrapper.emitted('navigate-source')?.[0]?.[0]).toMatchObject({source:{documentId:'doc-a',pageNumber:3,fileSha256:'a'.repeat(64),positions:[]}})
 wrapper.unmount();wrapper=mount(NoteSourceBlocks,{props:{sources:[block()],documents:[]}})
 expect(wrapper.text()).not.toContain('无法识别');expect(wrapper.text()).toContain('模拟问答数据')
})
it('shows unverified blocks without a fabricated navigation link',()=>{
 wrapper=mount(AiAnswerNoteBlock,{props:{block:{...block(),citations:[],evidenceState:'none',uncitedAcknowledged:true}}})
 expect(wrapper.text()).toContain('未核实');expect(wrapper.find('button').exists()).toBe(false)
})
