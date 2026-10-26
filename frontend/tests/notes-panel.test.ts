import {beforeEach,afterEach,it,expect,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {nextTick} from 'vue'
import NotesPanel from '../src/components/NotesPanel.vue'
import {notesApi,type NoteDTO} from '../src/notes'
import {auth} from '../src/auth'
import {ApiError} from '../src/api'
import * as navigation from '../src/reader/navigation'
import {readerTabs} from '../src/reader/state'
let wrapper:VueWrapper
const sourceBlock=(id:string,documentId:string,pageNumber:number)=>({id,kind:'pdf_excerpt' as const,createdAt:'2026-10-25',originalText:'Reliable source text',source:{documentId,title:'Source '+documentId,fileSha256:(documentId==='doc-b'?'b':'c').repeat(64),pageNumber,pageNumbers:[pageNumber],positions:[],contextRevision:1,precision:'page' as const},historical:false,requestFingerprint:'fingerprint'})
const preciseSourceBlock=(id:string,documentId:string,pageNumber:number)=>({...sourceBlock(id,documentId,pageNumber),source:{...sourceBlock(id,documentId,pageNumber).source,positions:[{pageNumber,textQuote:'Reliable source text',rects:[{x:.1,y:.2,width:.3,height:.04}],textRanges:[{item:2,start:0,end:20}]}]}})
const note=():NoteDTO=>({id:'note-a',title:'Research note',content:'<script>window.noteExecuted=true</script>',version:1,contentFormat:'plain-text',sourceSchemaVersion:1,sources:[],documents:[{id:'doc-a',title:'Document A'},{id:'doc-b',title:'Document B'}],createdAt:'2026-01-01',updatedAt:'2026-01-01'})
beforeEach(async()=>{vi.useFakeTimers();sessionStorage.clear();Object.defineProperty(window,'confirm',{configurable:true,writable:true,value:vi.fn(()=>false)});auth.user={id:'user-a',displayName:'Notes tester',email:'notes@example.com',createdAt:'2026-01-01'};vi.spyOn(notesApi,'config').mockResolvedValue({available:true,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'});vi.spyOn(notesApi,'list').mockImplementation(async()=>({items:[note()],page:1,pageSize:20,total:1}));vi.spyOn(notesApi,'get').mockResolvedValue(note());vi.spyOn(notesApi,'patch').mockImplementation(async(_id,body)=>({...note(),...body,version:body.version+1}));vi.spyOn(notesApi,'remove').mockResolvedValue();vi.spyOn(notesApi,'unlink').mockResolvedValue({...note(),documents:[{id:'doc-b',title:'Document B'}]});wrapper=mount(NotesPanel,{props:{documentId:'doc-a'},global:{stubs:{ReaderPanel:{props:['open'],template:'<aside v-show="open"><slot /></aside>'}}}});await flushPromises();(wrapper.vm as unknown as {toggle:()=>void}).toggle();await flushPromises()})
afterEach(()=>{wrapper.unmount();readerTabs.splice(0);auth.user=null;vi.clearAllTimers();vi.useRealTimers();vi.restoreAllMocks()})
async function openNote(){await wrapper.get('button[aria-label="打开笔记：Research note"]').trigger('click');await flushPromises()}
it('shows safe text fields and preserves content when the panel closes',async()=>{await openNote();expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toContain('<script>');expect(wrapper.find('script').exists()).toBe(false);await wrapper.get('textarea').setValue('Working draft');(wrapper.vm as unknown as {toggle:()=>void}).toggle();await nextTick();(wrapper.vm as unknown as {toggle:()=>void}).toggle();await nextTick();expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('Working draft');expect(wrapper.get('[data-testid="note-save-status"]').text()).toContain('等待自动保存')})
it('shows failed autosave and a usable explicit retry',async()=>{await openNote();vi.mocked(notesApi.patch).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Offline test'));await wrapper.get('textarea').setValue('Retained text');await vi.advanceTimersByTimeAsync(800);await flushPromises();expect(wrapper.get('[data-testid="note-save-status"]').text()).toContain('保存失败');expect(wrapper.text()).toContain('Offline test');const retry=wrapper.findAll('button').find(button=>button.text()==='重试保存')!;await retry.trigger('click');await flushPromises();expect(wrapper.get('[data-testid="note-save-status"]').text()).toBe('已保存')})
it('separates unlink from deleting all document associations with confirmation',async()=>{await openNote();const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);await wrapper.findAll('button').find(button=>button.text()==='删除笔记')!.trigger('click');await flushPromises();expect(confirm).toHaveBeenCalledWith(expect.stringContaining('所有文献'));expect(notesApi.remove).not.toHaveBeenCalled();await wrapper.findAll('button').find(button=>button.text()==='解除当前文献关联')!.trigger('click');await flushPromises();expect(notesApi.unlink).toHaveBeenCalledWith('note-a','doc-a');expect(notesApi.remove).not.toHaveBeenCalled()})
it('keeps conflict input unless server reload is explicitly confirmed',async()=>{await openNote();vi.mocked(notesApi.patch).mockRejectedValueOnce(new ApiError(409,'NOTE_VERSION_CONFLICT','Conflict'));await wrapper.get('textarea').setValue('My version');await vi.advanceTimersByTimeAsync(800);await flushPromises();const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);await wrapper.findAll('button').find(button=>button.text()==='载入服务器版本')!.trigger('click');await flushPromises();expect(confirm).toHaveBeenCalled();expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('My version');expect(wrapper.get('[data-testid="note-save-status"]').text()).toContain('冲突')})

it('opens an associated PDF through protected navigation and only changes the current badge',async()=>{
 await openNote();readerTabs.push({id:'doc-b',title:'Document B',page:3,mode:'continuous',scrollTop:0,zoom:1,zoomMode:'fit-width'})
 const navigate=vi.spyOn(navigation,'navigateReader').mockImplementation(async()=>{await wrapper.setProps({documentId:'doc-b'});return {status:'ok'}})
 const region=()=>wrapper.get('section[aria-label="关联文献"]')
 expect(region().get('h3').text()).toBe('关联文献（2）')
 expect(region().get('li[data-document-id="doc-a"]').text()).toContain('当前文献')
 await region().get('button[aria-label="打开关联文献：Document B"]').trigger('click');await flushPromises()
 expect(navigate).toHaveBeenCalledWith({documentId:'doc-b',pageNumber:3},{signal:expect.any(AbortSignal)})
 expect(region().findAll('li')).toHaveLength(2)
 expect(region().get('li[data-document-id="doc-b"]').text()).toContain('当前文献')
 expect(region().get('li[data-document-id="doc-a"]').text()).not.toContain('当前文献')
 expect(notesApi.patch).not.toHaveBeenCalled();expect(notesApi.unlink).not.toHaveBeenCalled();expect(notesApi.remove).not.toHaveBeenCalled()
})
it('reports an unavailable related PDF without changing associations or removing the current note',async()=>{
 await openNote();vi.spyOn(navigation,'navigateReader').mockResolvedValue({status:'error',code:'DOCUMENT_NOT_FOUND',message:'文献不可访问'})
 await wrapper.get('section[aria-label="关联文献"] button[aria-label="打开关联文献：Document B"]').trigger('click');await flushPromises()
 expect(wrapper.get('[data-testid="note-navigation-error"]').text()).toBe('文献不可访问')
 expect(wrapper.get('section[aria-label="关联文献"] h3').text()).toBe('关联文献（2）')
 expect(wrapper.get('section[aria-label="关联文献"] li[data-document-id="doc-a"]').text()).toContain('当前文献')
 expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe(note().content)
 expect(notesApi.unlink).not.toHaveBeenCalled();expect(notesApi.remove).not.toHaveBeenCalled()
})
it('blocks association navigation when autosave failed and preserves the current text',async()=>{
 await openNote();const navigate=vi.spyOn(navigation,'navigateReader')
 vi.mocked(notesApi.patch).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Offline save'))
 await wrapper.get('textarea').setValue('Keep unsaved note');await vi.advanceTimersByTimeAsync(800);await flushPromises()
 await wrapper.get('section[aria-label="关联文献"] button[aria-label="打开关联文献：Document B"]').trigger('click');await flushPromises()
 expect(navigate).not.toHaveBeenCalled();expect(wrapper.get('[data-testid="note-navigation-error"]').text()).toContain('笔记尚未保存')
 expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('Keep unsaved note')
})

it('opens a personal-note associated PDF without linking that note to the origin document',async()=>{
 const personal={...note(),id:'personal-note',title:'Other personal note',documents:[{id:'doc-b',title:'Document B'}]}
 vi.mocked(notesApi.list).mockImplementation(async(documentId)=>({items:documentId===null?[personal]:[note()],page:1,pageSize:20,total:1}))
 vi.mocked(notesApi.get).mockImplementation(async(id)=>id==='personal-note'?personal:note())
 const link=vi.spyOn(notesApi,'link')
 vi.spyOn(navigation,'navigateReader').mockImplementation(async()=>{await wrapper.setProps({documentId:'doc-b'});return {status:'ok'}})
 await openNote()
 await wrapper.findAll('button').find(button=>button.text()==='关联已有笔记')!.trigger('click');await flushPromises()
 const picker=wrapper.get('section[aria-label="个人已有笔记"]')
 await picker.get('button[aria-label="打开关联文献：Document B"]').trigger('click');await flushPromises()
 expect(link).not.toHaveBeenCalled();expect(notesApi.unlink).not.toHaveBeenCalled()
 expect((wrapper.get('input[aria-label="笔记标题"]').element as HTMLInputElement).value).toBe('Other personal note')
 expect(wrapper.get('section[aria-label="关联文献"] h3').text()).toBe('关联文献（1）')
})

it('flushes a dirty draft, navigates by immutable source and restores an unassociated note',async()=>{
 const sourced={...note(),content:'Initial body',documents:[{id:'doc-a',title:'Document A'}],sources:[sourceBlock('source-b','doc-b',3)]}
 let persisted=sourced
 vi.mocked(notesApi.get).mockImplementation(async()=>persisted)
 vi.mocked(notesApi.patch).mockImplementation(async(_id,body)=>(persisted={...persisted,...body,version:body.version+1}))
 const link=vi.spyOn(notesApi,'link')
 await openNote()
 const navigate=vi.spyOn(navigation,'navigateReader').mockImplementation(async()=>{await wrapper.setProps({documentId:'doc-b'});return {status:'ok'}})
 await wrapper.get('textarea').setValue('Draft saved before source navigation')
 await wrapper.get('button[aria-label="查看原文：Source doc-b，PDF 第 3 页"]').trigger('click');await flushPromises()
 expect(notesApi.patch).toHaveBeenCalledWith('note-a',expect.objectContaining({content:'Draft saved before source navigation'}))
 expect(navigate).toHaveBeenCalledWith({documentId:'doc-b',pageNumber:3,fileSha256:'b'.repeat(64)},{signal:expect.any(AbortSignal)})
 expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('Draft saved before source navigation')
 expect(wrapper.get('[data-testid="note-navigation-success"]').text()).toContain('第 3 页')
 expect(link).not.toHaveBeenCalled();expect(notesApi.unlink).not.toHaveBeenCalled()
})

it('cancels an older source request when another source is clicked quickly',async()=>{
 const sourced={...note(),sources:[sourceBlock('source-b','doc-b',2),sourceBlock('source-c','doc-c',3)]}
 vi.mocked(notesApi.get).mockResolvedValue(sourced);await openNote()
 const signals:AbortSignal[]=[]
 vi.spyOn(navigation,'navigateReader').mockImplementation(async(target,options)=>{
  const signal=options?.signal!;signals.push(signal)
  if(target.documentId==='doc-b')return new Promise(resolve=>signal.addEventListener('abort',()=>resolve({status:'error',code:'STALE_CONTEXT',message:'cancelled'}),{once:true}))
  await wrapper.setProps({documentId:'doc-c'});return {status:'ok'}
 })
 await wrapper.get('button[aria-label="查看原文：Source doc-b，PDF 第 2 页"]').trigger('click');await flushPromises()
 await wrapper.get('button[aria-label="查看原文：Source doc-c，PDF 第 3 页"]').trigger('click');await flushPromises()
 expect(signals[0]?.aborted).toBe(true);expect(signals[1]?.aborted).toBe(false)
 expect(wrapper.get('[data-testid="note-navigation-success"]').text()).toContain('第 3 页')
 expect(wrapper.find('[data-testid="note-navigation-error"]').exists()).toBe(false)
})
it('forwards reliable selection metadata and reports exact positioning without changing the note source',async()=>{
 const block=preciseSourceBlock('source-b','doc-b',3),sourced={...note(),documents:[{id:'doc-a',title:'Document A'}],sources:[block]}
 vi.mocked(notesApi.get).mockResolvedValue(sourced);await openNote()
 const navigate=vi.spyOn(navigation,'navigateReader').mockImplementation(async()=>{await wrapper.setProps({documentId:'doc-b'});return {status:'ok',precision:'exact',message:'已精确定位来源文献 PDF 第 3 页的原文。'}})
 await wrapper.get('button[aria-label="查看原文：Source doc-b，PDF 第 3 页"]').trigger('click');await flushPromises()
 expect(navigate).toHaveBeenCalledWith({documentId:'doc-b',pageNumber:3,fileSha256:'b'.repeat(64),position:block.source.positions[0]},{signal:expect.any(AbortSignal)})
 expect(wrapper.get('[data-testid="note-navigation-success"]').text()).toContain('精确定位')
 expect(notesApi.patch).not.toHaveBeenCalled();expect(notesApi.unlink).not.toHaveBeenCalled()
})
