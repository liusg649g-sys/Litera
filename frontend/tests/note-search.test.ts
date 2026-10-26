import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest'
import {flushPromises,mount,type VueWrapper} from '@vue/test-utils'
import NotesPanel from '../src/components/NotesPanel.vue'
import {ApiError} from '../src/api'
import {auth} from '../src/auth'
import {createNotesController,notesApi,type NoteDTO,type NoteSearchPage,type NotesApi} from '../src/notes'

const note=(id='note-one',title='Saved note',content='Saved content'):NoteDTO=>({id,title,content,version:1,contentFormat:'plain-text',sourceSchemaVersion:1,sources:[],documents:[{id:'doc-a',title:'Document A'},{id:'doc-b',title:'Document B'}],createdAt:'2026-01-01',updatedAt:'2026-01-01'})
const result=(query:string,id='note-two'):NoteSearchPage=>({query,page:1,pageSize:20,total:1,items:[{...note(id,'Microscopy note','Optical microscopy body'),matches:[{field:'source_translation',label:'译文',snippet:'活细胞显微成像译文',matchStart:3,matchEnd:7,leadingEllipsis:false,trailingEllipsis:false,sourceBlockId:'block-a',documentId:'doc-b',pageNumber:7}]}]})

function setup(){
 const records=new Map([['note-one',note()],['note-two',note('note-two','Microscopy note','Optical microscopy body')]])
 const transport:NotesApi={
  config:vi.fn().mockResolvedValue({available:true,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'}),
  list:vi.fn().mockResolvedValue({items:[note()],page:1,pageSize:20,total:1}),
  search:vi.fn().mockImplementation(async query=>result(query)),
  get:vi.fn().mockImplementation(async id=>structuredClone(records.get(id)!)),
  create:vi.fn(),patch:vi.fn().mockImplementation(async(id,input)=>({...records.get(id)!,...input,version:input.version+1})),
  link:vi.fn(),unlink:vi.fn(),remove:vi.fn(),
 }
 return {transport,model:createNotesController(transport,sessionStorage,800,350)}
}
async function ready(model:ReturnType<typeof createNotesController>){await model.setUser('user-a');await model.setDocument('doc-a');await model.setOpen(true);await model.choose('note-one')}

beforeEach(()=>{vi.useFakeTimers();sessionStorage.clear()})
afterEach(()=>{auth.user=null;vi.clearAllTimers();vi.useRealTimers();vi.restoreAllMocks()})

describe('note search controller',()=>{
 it('debounces input, invalidates stale responses, and clears back to the normal list',async()=>{
  const {model,transport}=setup();await ready(model)
  let release!:(value:NoteSearchPage)=>void
  vi.mocked(transport.search).mockImplementationOnce(()=>new Promise(resolve=>release=resolve))
  model.setSearchInput('micro');await vi.advanceTimersByTimeAsync(349);expect(transport.search).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1);expect(transport.search).toHaveBeenCalledWith('micro',1)
  model.setSearchInput('细胞');await vi.advanceTimersByTimeAsync(350)
  expect(transport.search).toHaveBeenLastCalledWith('细胞',1)
  release(result('micro','stale-note'));await flushPromises()
  expect(model.state.search.items[0]?.id).toBe('note-two');expect(model.state.search.query).toBe('细胞')
  model.clearSearch();expect(model.state.search.input).toBe('');expect(model.state.search.items).toHaveLength(0)
  expect(model.state.list.items[0]?.id).toBe('note-one');model.dispose()
 })
 it('reports failures and retries without writing a note',async()=>{
  const {model,transport}=setup();await ready(model)
  vi.mocked(transport.search).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Search offline'))
  model.setSearchInput('optical');await vi.advanceTimersByTimeAsync(350);await flushPromises()
  expect(model.state.search.error).toBe('Search offline');expect(transport.patch).not.toHaveBeenCalled()
  expect(await model.runSearch()).toBe(true);expect(model.state.search.items).toHaveLength(1);expect(transport.patch).not.toHaveBeenCalled();model.dispose()
 })
 it('never overwrites a dirty draft and reuses the save guard before opening a result',async()=>{
  const {model,transport}=setup();await ready(model)
  model.edit('content','Unsaved local draft');model.setSearchInput('optical');await vi.advanceTimersByTimeAsync(350);await flushPromises()
  expect(model.state.editor?.content).toBe('Unsaved local draft');expect(transport.patch).not.toHaveBeenCalled()
  vi.mocked(transport.patch).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Save blocked'))
  expect(await model.choose('note-two')).toBe(false)
  expect(model.state.editor?.note.id).toBe('note-one');expect(model.state.editor?.content).toBe('Unsaved local draft')
  expect(transport.get).not.toHaveBeenCalledWith('note-two');model.dispose()
 })
})

describe('note search panel',()=>{
 let wrapper:VueWrapper
 beforeEach(async()=>{
  auth.user={id:'user-a',displayName:'Search tester',email:'search@example.com',createdAt:'2026-01-01'}
  vi.spyOn(notesApi,'config').mockResolvedValue({available:true,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'})
  vi.spyOn(notesApi,'list').mockResolvedValue({items:[note()],page:1,pageSize:20,total:1})
  vi.spyOn(notesApi,'search').mockImplementation(async query=>result(query))
  vi.spyOn(notesApi,'get').mockImplementation(async id=>note(id,id==='note-two'?'Microscopy note':'Saved note',id==='note-two'?'Optical microscopy body':'Saved content'))
  wrapper=mount(NotesPanel,{props:{documentId:'doc-a'},global:{stubs:{ReaderPanel:{props:['open'],template:'<aside v-show="open"><slot /></aside>'}}}})
  await flushPromises();(wrapper.vm as unknown as {toggle:()=>void}).toggle();await flushPromises()
 })
 afterEach(()=>wrapper?.unmount())
 it('shows safe field-labelled highlighting, opens a result, and restores the document list when cleared',async()=>{
  await wrapper.get('input[aria-label="搜索个人笔记关键词"]').setValue('成像译文')
  await vi.advanceTimersByTimeAsync(349);expect(notesApi.search).not.toHaveBeenCalled()
  await vi.advanceTimersByTimeAsync(1);await flushPromises()
  const results=wrapper.get('[data-testid="note-search-results"]')
  expect(results.text()).toContain('译文');expect(results.text()).toContain('PDF 第 7 页')
  expect(results.get('mark').text()).toBe('显微成像')
  await results.get('button[aria-label="打开搜索结果：Microscopy note"]').trigger('click');await flushPromises()
  expect(notesApi.get).toHaveBeenCalledWith('note-two');expect(wrapper.get('input[aria-label="笔记标题"]').element).toHaveProperty('value','Microscopy note')
  await wrapper.get('button[aria-label="清空笔记搜索"]').trigger('click')
  expect(wrapper.find('[data-testid="note-search-results"]').exists()).toBe(false)
  expect(wrapper.get('section[aria-label="当前文献笔记列表"]').text()).toContain('Saved note')
 })
})
