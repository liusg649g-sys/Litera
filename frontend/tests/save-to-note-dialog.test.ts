import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import SaveToNoteDialog from '../src/components/SaveToNoteDialog.vue'
import { noteCaptureApi, type CaptureConfig, type NoteCaptureDraft, type CaptureSource } from '../src/notes/captures'
import { ApiError } from '../src/api'
import type { NoteDTO } from '../src/notes'
let wrapper:VueWrapper
const note=(documents=[{id:'doc-a',title:'Document A'}]):NoteDTO=>({id:'note-a',title:'Existing note',content:'Personal body',contentFormat:'plain-text',sourceSchemaVersion:1,version:4,sources:[],documents,createdAt:'2026-10-23',updatedAt:'2026-10-23'})
const draft=():NoteCaptureDraft<CaptureSource>=>({title:'Document A',source:{kind:'pdf_excerpt',documentId:'doc-a',pageNumber:3,originalText:'Optical microscopy',positions:[],contextRevision:8,historical:false,confirmHistorical:false}})
const config:CaptureConfig={available:true,formatVersion:1,maxOriginalLength:6000,maxTranslatedLength:20000,maxBlocks:100,maxSourceBytes:1048576}
async function open(preferred:NoteDTO|null=null,source=draft()){wrapper=mount(SaveToNoteDialog,{props:{draft:source,preferredNote:preferred,ownerId:'user-a'},attachTo:document.body});await flushPromises();return wrapper}
async function submit(){await wrapper.get('form').trigger('submit');await flushPromises()}
function button(text:string){return wrapper.findAll('button').find(item=>item.text()===text)!}
beforeEach(()=>{
 vi.spyOn(noteCaptureApi,'config').mockResolvedValue(config)
 vi.spyOn(noteCaptureApi,'list').mockResolvedValue({items:[note()],page:1,pageSize:20,total:1})
 vi.spyOn(noteCaptureApi,'get').mockResolvedValue(note())
 vi.spyOn(noteCaptureApi,'save').mockResolvedValue({note:note(),blockId:'block-a',created:true,linked:true,replayed:false})
})
afterEach(()=>{wrapper?.unmount();vi.restoreAllMocks()})
it('creates a new note only on explicit save with the frozen source',async()=>{
 await open();expect(wrapper.get('dialog').attributes('open')).toBeDefined();expect(noteCaptureApi.save).not.toHaveBeenCalled()
 await wrapper.get('[aria-label="新笔记标题"]').setValue('My excerpt');await submit()
 expect(noteCaptureApi.save).toHaveBeenCalledOnce()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0]).toMatchObject({newNoteTitle:'My excerpt',version:null,associationMode:'link',source:draft().source})
 expect(wrapper.emitted('captured')?.[0]?.[0]).toEqual(note())
})
it('loads the recommended latest note version without rewriting its body',async()=>{
 await open({...note(),version:1});expect(noteCaptureApi.get).toHaveBeenCalledWith('note-a');await submit()
 const request=vi.mocked(noteCaptureApi.save).mock.calls[0]![0]
 expect(request).toMatchObject({noteId:'note-a',version:4,newNoteTitle:null,associationMode:'keep'});expect(request).not.toHaveProperty('content')
})
it('requires explicit association consent and permits source-only storage',async()=>{
 vi.mocked(noteCaptureApi.get).mockResolvedValue(note([{id:'doc-b',title:'Document B'}]));await open(note())
 expect(wrapper.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
 await wrapper.get('input[value="keep"]').setValue(true);await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0].associationMode).toBe('keep')
})
it('requires historical confirmation and labels isolated Mock translations',async()=>{
 const source=draft();Object.assign(source.source,{kind:'translation_excerpt',translatedText:'Mock translation',sourceLanguage:'en',targetLanguage:'zh',historical:true,translationProof:{version:1,issuedAt:123,signature:'a'.repeat(64),provenance:'isolated_mock'}})
 await open(null,source);expect(wrapper.text()).toContain('隔离 Mock 译文（非真实模型）')
 expect(wrapper.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
 await wrapper.get('input[type="checkbox"]').setValue(true);await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0].source).toMatchObject({historical:true,confirmHistorical:true,documentId:'doc-a',pageNumber:3})
})
it('retries an unknown outcome with the same immutable operation and payload',async()=>{
 vi.mocked(noteCaptureApi.save).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Network unavailable'));await open();await submit()
 const initial=structuredClone(vi.mocked(noteCaptureApi.save).mock.calls[0]![0]);expect(wrapper.text()).toContain('保存结果尚未确认')
 expect(wrapper.get('fieldset').attributes('disabled')).toBeDefined()
 await button('重试保存').trigger('click');await flushPromises()
 expect(noteCaptureApi.save).toHaveBeenCalledTimes(2);expect(vi.mocked(noteCaptureApi.save).mock.calls[1]![0]).toEqual(initial)
})
it('blocks duplicate clicks and ignores a late response for a previous owner',async()=>{
 let release!:(value:Awaited<ReturnType<typeof noteCaptureApi.save>>)=>void
 vi.mocked(noteCaptureApi.save).mockImplementation(()=>new Promise(resolve=>release=resolve));await open();await submit();await submit()
 expect(noteCaptureApi.save).toHaveBeenCalledOnce();await wrapper.setProps({ownerId:'user-b',draft:null})
 release({note:note(),blockId:'old',created:true,linked:true,replayed:false});await flushPromises();expect(wrapper.emitted('captured')).toBeUndefined()
})
it('requires explicit conflict reload and confirms before saving with latest version',async()=>{
 vi.mocked(noteCaptureApi.save).mockRejectedValueOnce(new ApiError(409,'NOTE_VERSION_CONFLICT','Version conflict'));await open(note());await submit()
 expect(button('重新读取目标笔记').exists()).toBe(true);expect(noteCaptureApi.save).toHaveBeenCalledOnce()
 vi.mocked(noteCaptureApi.get).mockResolvedValue({...note(),version:5});await button('重新读取目标笔记').trigger('click');await flushPromises()
 expect(noteCaptureApi.save).toHaveBeenCalledOnce();await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[1]![0].version).toBe(5)
 expect(vi.mocked(noteCaptureApi.save).mock.calls[1]![0].operationId).not.toBe(vi.mocked(noteCaptureApi.save).mock.calls[0]![0].operationId)
})
it('supports title filtering and reads selected personal note before append',async()=>{
 await open();await wrapper.findAll('input[type="radio"]')[1]!.setValue(true);await flushPromises()
 await wrapper.get('[aria-label="搜索已有笔记标题"]').setValue('Existing');await button('搜索笔记').trigger('click');await flushPromises()
 expect(noteCaptureApi.list).toHaveBeenLastCalledWith('Existing',1)
 await wrapper.get('[aria-label="选择笔记：Existing note"]').trigger('click');await flushPromises();await submit()
 expect(vi.mocked(noteCaptureApi.save).mock.calls[0]![0]).toMatchObject({noteId:'note-a',version:4,newNoteTitle:null})
})
it('preserves source on failure and disables old undeployed servers',async()=>{
 vi.mocked(noteCaptureApi.save).mockRejectedValueOnce(new ApiError(400,'INVALID_REQUEST','Unable to save'));await open();await submit()
 expect(wrapper.get('[data-testid="note-capture-original"]').text()).toBe(draft().source.originalText);expect(wrapper.text()).toContain('Unable to save')
 await submit();expect(noteCaptureApi.save).toHaveBeenCalledTimes(2);wrapper.unmount()
 vi.mocked(noteCaptureApi.config).mockRejectedValueOnce(new ApiError(404,'NOT_FOUND','Not found'));await open()
 expect(wrapper.text()).toContain('摘录功能尚未部署');expect(wrapper.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
})

it('blocks unknown source schema versions rather than merely showing a warning',async()=>{
 vi.mocked(noteCaptureApi.config).mockResolvedValue({...config,formatVersion:2} as unknown as CaptureConfig)
 await open()
 expect(wrapper.text()).toContain('摘录功能尚未部署')
 expect(wrapper.get('[aria-label="保存摘录"]').attributes('disabled')).toBeDefined()
 await submit();expect(noteCaptureApi.save).not.toHaveBeenCalled()
})
