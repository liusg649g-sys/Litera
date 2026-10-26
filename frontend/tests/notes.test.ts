import {afterEach,beforeEach,describe,it,expect,vi} from 'vitest'
import {ApiError} from '../src/api'
import {createNotesController,type NoteDTO,type NotesApi,type NotesPage,type NotesConfig,type NoteSearchPage} from '../src/notes'
const base=():NoteDTO=>({id:'note-one',title:'Saved note',content:'Saved content',version:1,contentFormat:'plain-text',sourceSchemaVersion:1,sources:[],documents:[{id:'doc-a',title:'Document A'}],createdAt:'2026-01-01',updatedAt:'2026-01-01'})
const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value))
function setup(){
 const records=new Map<string,NoteDTO>([['note-one',base()]])
 const transport:NotesApi={
  config:vi.fn().mockResolvedValue({available:true,contentMaxLength:100000,titleMaxLength:200,contentFormat:'plain-text'}),
  list:vi.fn().mockImplementation(async(documentId:string|null,page:number)=>({items:[...records.values()].filter(note=>!documentId||note.documents.some(doc=>doc.id===documentId)).map(clone),page,pageSize:20,total:[...records.values()].filter(note=>!documentId||note.documents.some(doc=>doc.id===documentId)).length} as NotesPage)),
  search:vi.fn().mockImplementation(async(query:string,page:number)=>({items:[...records.values()].filter(note=>(note.title+' '+note.content).toLowerCase().includes(query.toLowerCase())).map(note=>({...clone(note),matches:[{field:'content',label:'正文',snippet:note.content,matchStart:0,matchEnd:Math.min(query.length,note.content.length),leadingEllipsis:false,trailingEllipsis:false}]})),query,page,pageSize:20,total:[...records.values()].filter(note=>(note.title+' '+note.content).toLowerCase().includes(query.toLowerCase())).length} as NoteSearchPage)),
  get:vi.fn().mockImplementation(async(id:string)=>clone(records.get(id)!)),
  create:vi.fn().mockImplementation(async body=>{let note=records.get(body.id);if(!note){note={...base(),id:body.id,title:body.title,content:body.content,documents:[{id:body.documentId,title:'Document A'}]};records.set(note.id,note)}return clone(note)}),
  patch:vi.fn().mockImplementation(async(id,body)=>{const note=records.get(id)!;if(note.version!==body.version)throw new ApiError(409,'NOTE_VERSION_CONFLICT','Version conflict');Object.assign(note,{title:body.title,content:body.content,version:note.version+1});return clone(note)}),
  link:vi.fn().mockImplementation(async(id,doc)=>{const note=records.get(id)!;if(!note.documents.some(document=>document.id===doc))note.documents.push({id:doc,title:'Document B'});return clone(note)}),
  unlink:vi.fn().mockImplementation(async(id,doc)=>{const note=records.get(id)!;note.documents=note.documents.filter(document=>document.id!==doc);return clone(note)}),
  remove:vi.fn().mockImplementation(async id=>{records.delete(id)}),
 }
 const model=createNotesController(transport,sessionStorage)
 return {model,transport,records}
}
async function ready(model:ReturnType<typeof createNotesController>){await model.setUser('user-a');await model.setDocument('doc-a');await model.setOpen(true);await model.choose('note-one')}
beforeEach(()=>{vi.useFakeTimers();sessionStorage.clear()});afterEach(()=>{vi.clearAllTimers();vi.useRealTimers()})
describe('notes autosave with Mock API and isolated browser storage',()=>{
 it('only autosaves after800ms and keeps closing independent from editor state',async()=>{const {model,transport}=setup();await ready(model);model.edit('content','New body');await vi.advanceTimersByTimeAsync(799);expect(transport.patch).not.toHaveBeenCalled();await model.setOpen(false);expect(model.state.editor?.content).toBe('New body');await vi.advanceTimersByTimeAsync(1);expect(transport.patch).toHaveBeenCalledWith('note-one',{version:1,title:'Saved note',content:'New body'});expect(model.state.editor?.dirty).toBe(false);await model.setOpen(true);expect(model.state.editor?.content).toBe('New body');model.dispose()})
 it('serializes a slow save then writes only the newest edited snapshot',async()=>{const {model,transport,records}=setup();await ready(model);let release!:(value:NoteDTO)=>void;vi.mocked(transport.patch).mockImplementationOnce(()=>new Promise(resolve=>release=resolve));model.edit('content','First');await vi.advanceTimersByTimeAsync(800);model.edit('content','Second');model.edit('content','Latest');await vi.advanceTimersByTimeAsync(800);expect(transport.patch).toHaveBeenCalledTimes(1);const committed={...base(),content:'First',version:2};records.set('note-one',committed);release(clone(committed));await vi.advanceTimersByTimeAsync(0);expect(transport.patch).toHaveBeenCalledTimes(2);expect(vi.mocked(transport.patch).mock.calls[1]![1]).toMatchObject({version:2,content:'Latest'});expect(model.state.editor?.content).toBe('Latest');expect(model.state.editor?.dirty).toBe(false);model.dispose()})
 it('keeps a failed draft, blocks navigation, and retries only explicitly',async()=>{const {model,transport}=setup();await ready(model);vi.mocked(transport.patch).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Network unavailable'));model.edit('content','Retained offline');await vi.advanceTimersByTimeAsync(800);expect(model.state.editor?.error).toContain('Network');expect(sessionStorage.getItem('litera:notes-draft:user-a:note-one')).toContain('Retained offline');expect(await model.beforeLeave()).toBe(false);await vi.advanceTimersByTimeAsync(5000);expect(transport.patch).toHaveBeenCalledTimes(1);expect(await model.retrySave()).toBe(true);expect(model.state.editor?.dirty).toBe(false);expect(sessionStorage.getItem('litera:notes-draft:user-a:note-one')).toBeNull();model.dispose()})
 it('restores only the current owner draft after refresh and preserves it across auth loss',async()=>{const first=setup();await ready(first.model);first.model.edit('content','Private local draft');await first.model.setUser('');expect(sessionStorage.getItem('litera:notes-draft:user-a:note-one')).toContain('Private local draft');await first.model.setUser('other-user');await first.model.choose('note-one');expect(first.model.state.editor?.content).toBe('Saved content');first.model.dispose();const second=setup();await ready(second.model);expect(second.model.state.editor?.content).toBe('Private local draft');expect(second.model.state.editor?.dirty).toBe(true);second.model.dispose()})
 it('preserves409 input and requires explicit server reload instead of overwriting',async()=>{const {model,transport,records}=setup();await ready(model);records.set('note-one',{...base(),content:'Other window',version:2});model.edit('content','My conflict draft');await vi.advanceTimersByTimeAsync(800);expect(model.state.editor?.conflict).toBe(true);expect(model.state.editor?.content).toBe('My conflict draft');expect(await model.retrySave()).toBe(false);expect(transport.patch).toHaveBeenCalledOnce();expect(await model.reload()).toBe(true);expect(model.state.editor?.content).toBe('Other window');expect(model.state.editor?.dirty).toBe(false);model.dispose()})
 it('detects a restored draft based on an older server version',async()=>{sessionStorage.setItem('litera:notes-draft:user-a:note-one',JSON.stringify({schema:1,userId:'user-a',noteId:'note-one',version:1,title:'Mine',content:'Mine'}));const {model,transport,records}=setup();records.set('note-one',{...base(),version:3,content:'Remote'});await ready(model);expect(model.state.editor?.conflict).toBe(true);await vi.advanceTimersByTimeAsync(2000);expect(transport.patch).not.toHaveBeenCalled();expect(model.state.editor?.content).toBe('Mine');model.dispose()})
 it('reuses a single note across documents and unlink does not delete its body',async()=>{const {model,transport,records}=setup();await ready(model);await model.setDocument('doc-b');await model.link('note-one');expect(model.state.editor?.note.id).toBe('note-one');expect(records.size).toBe(1);expect(model.state.editor?.note.documents).toHaveLength(2);await model.unlink();expect(transport.remove).not.toHaveBeenCalled();expect(records.get('note-one')?.content).toBe('Saved content');expect(records.get('note-one')?.documents.map(document=>document.id)).toEqual(['doc-a']);model.dispose()})
 it('retries an ambiguous creation with the same client UUID',async()=>{const {model,transport}=setup();await model.setUser('user-a');await model.setDocument('doc-a');vi.mocked(transport.create).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Network unavailable'));expect(await model.create()).toBe(false);expect(await model.create()).toBe(true);expect(vi.mocked(transport.create).mock.calls[0]![0].id).toBe(vi.mocked(transport.create).mock.calls[1]![0].id);model.dispose()})
 it('ignores a late save from an old authenticated scope',async()=>{const {model,transport}=setup();await ready(model);let release!:(note:NoteDTO)=>void;vi.mocked(transport.patch).mockImplementationOnce(()=>new Promise(resolve=>release=resolve));model.edit('content','Old scope');await vi.advanceTimersByTimeAsync(800);await model.setUser('user-b');await model.choose('note-one');release({...base(),title:'Old title',content:'Old scope',version:2});await vi.advanceTimersByTimeAsync(0);expect(model.state.userId).toBe('user-b');expect(model.state.editor?.content).toBe('Saved content');model.dispose()})
 it('gates unavailable old servers without sending CRUD requests',async()=>{const {model,transport}=setup();vi.mocked(transport.config).mockRejectedValueOnce(new ApiError(404,'HTTP_ERROR','Not Found'));await model.setUser('user-a');await model.setDocument('doc-a');await model.setOpen(true);expect(model.state.unavailable).toContain('尚未部署');expect(await model.create()).toBe(false);expect(transport.list).not.toHaveBeenCalled();expect(transport.create).not.toHaveBeenCalled();model.dispose()})
 it('reports browser backup quota problems rather than claiming draft retention',async()=>{const broken={getItem:()=>null,setItem:()=>{throw new Error('Quota')},removeItem:()=>{}} as unknown as Storage;const {transport}=setup();const model=createNotesController(transport,broken);await ready(model);model.edit('content','Unsaved');expect(model.state.backupWarning).toContain('无法保留');model.dispose()})
})


it('loads the document if the panel is opened while configuration is still pending',async()=>{const {model,transport}=setup();let finish!:(value:NotesConfig)=>void;vi.mocked(transport.config).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve));const loading=model.setUser('user-a');await model.setDocument('doc-a');await model.setOpen(true);expect(transport.list).not.toHaveBeenCalled();finish({available:true,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'});await loading;expect(model.state.list.items).toHaveLength(1);model.dispose()})

it('keeps the newest note selection when an older GET returns later',async()=>{
 const {model,transport}=setup();await ready(model)
 let first!:(note:NoteDTO)=>void,second!:(note:NoteDTO)=>void
 vi.mocked(transport.get).mockImplementationOnce(()=>new Promise(resolve=>first=resolve)).mockImplementationOnce(()=>new Promise(resolve=>second=resolve))
 const oldChoice=model.choose('note-one');await vi.advanceTimersByTimeAsync(0)
 const newChoice=model.choose('note-two');await vi.advanceTimersByTimeAsync(0)
 second({...base(),id:'note-two',title:'Second note',content:'Second body'});expect(await newChoice).toBe(true)
 first({...base(),title:'Late old response'});expect(await oldChoice).toBe(false)
 expect(model.state.editor?.note.id).toBe('note-two');expect(model.state.editor?.title).toBe('Second note');model.dispose()
})

it('does not let an old selection clear the latest pending GET busy state',async()=>{
 const {model,transport}=setup();await ready(model)
 let first!:(note:NoteDTO)=>void,second!:(note:NoteDTO)=>void
 vi.mocked(transport.get).mockImplementationOnce(()=>new Promise(resolve=>first=resolve)).mockImplementationOnce(()=>new Promise(resolve=>second=resolve))
 const oldChoice=model.choose('note-one');await vi.advanceTimersByTimeAsync(0)
 const newChoice=model.choose('note-two');await vi.advanceTimersByTimeAsync(0)
 first(base());expect(await oldChoice).toBe(false);expect(model.state.busy).toBe(true)
 second({...base(),id:'note-two'});expect(await newChoice).toBe(true);expect(model.state.busy).toBe(false);model.dispose()
})

it('invalidates an in-flight selection when the document changes',async()=>{
 const {model,transport}=setup();await ready(model);let finish!:(note:NoteDTO)=>void
 vi.mocked(transport.get).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve))
 const choice=model.choose('note-one');await vi.advanceTimersByTimeAsync(0)
 expect(await model.setDocument('doc-b')).toBe(true);expect(model.state.busy).toBe(false)
 finish(base());expect(await choice).toBe(false);expect(model.state.editor).toBeNull();expect(model.state.documentId).toBe('doc-b');model.dispose()
})

it('does not replace a failed dirty editor when retrying an ambiguous create',async()=>{
 const {model,transport}=setup();await ready(model)
 vi.mocked(transport.create).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Create response lost'))
 expect(await model.create()).toBe(false)
 vi.mocked(transport.patch).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Save failed'))
 model.edit('content','Keep this existing note draft');await vi.advanceTimersByTimeAsync(800)
 expect(await model.create()).toBe(false);expect(transport.create).toHaveBeenCalledTimes(1)
 expect(model.state.editor?.note.id).toBe('note-one');expect(model.state.editor?.content).toBe('Keep this existing note draft')
 expect(sessionStorage.getItem('litera:notes-draft:user-a:note-one')).toContain('Keep this existing note draft');model.dispose()
})

describe('unlink/delete read consistency regressions',()=>{
 it('updates the personal cached document associations immediately after unlink',async()=>{
  const {model,records}=setup();records.get('note-one')!.documents.push({id:'doc-b',title:'Document B'})
  await ready(model);await model.loadPersonal(1)
  expect(await model.unlink()).toBe(true)
  expect(model.state.list.items).toHaveLength(0)
  expect(model.state.personal.items[0]!.documents.map(document=>document.id)).toEqual(['doc-b'])
  expect(records.get('note-one')!.content).toBe('Saved content');model.dispose()
 })
 it('removes deleted notes from the open personal chooser as well as the document list',async()=>{
  const {model}=setup();await ready(model);await model.loadPersonal(1)
  expect(await model.remove()).toBe(true)
  expect(model.state.list.items).toHaveLength(0);expect(model.state.personal.items).toHaveLength(0)
  expect(model.state.personal.total).toBe(0);model.dispose()
 })
 it('does not let an earlier list GET resurrect a successfully unlinked note',async()=>{
  const {model,transport}=setup();await ready(model);let finish!:(page:NotesPage)=>void
  vi.mocked(transport.list).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve))
  const oldRead=model.refreshList(1)
  expect(await model.unlink()).toBe(true);expect(model.state.list.items).toHaveLength(0)
  finish({items:[base()],page:1,pageSize:20,total:1});await oldRead
  expect(model.state.list.items).toHaveLength(0);expect(model.state.list.total).toBe(0);model.dispose()
 })
 it('invalidates a pending document switch when the route returns to the current document',async()=>{
  const {model,transport}=setup();await ready(model);let release!:(note:NoteDTO)=>void
  vi.mocked(transport.patch).mockImplementationOnce(()=>new Promise(resolve=>release=resolve))
  model.edit('content','Saving during navigation');await vi.advanceTimersByTimeAsync(800)
  const towardsB=model.setDocument('doc-b');await vi.advanceTimersByTimeAsync(0)
  expect(await model.setDocument('doc-a')).toBe(true)
  release({...base(),content:'Saving during navigation',version:2});await towardsB
  expect(model.state.documentId).toBe('doc-a');model.dispose()
 })
})


it('keeps unlink success distinct from a failed list reload and retries only the read',async()=>{
 const {model,transport,records}=setup();records.get('note-one')!.documents.push({id:'doc-b',title:'Document B'});await ready(model);await model.loadPersonal(1)
 vi.mocked(transport.list).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Read offline'))
 expect(await model.unlink()).toBe(true);expect(model.state.list.items).toHaveLength(0)
 expect(model.state.personal.items[0]!.documents.map(document=>document.id)).toEqual(['doc-b'])
 expect(model.state.success).toContain('已从当前文献解除关联');expect(model.state.error).toBe('Read offline')
 await model.refreshList();expect(model.state.error).toBe('');expect(transport.unlink).toHaveBeenCalledOnce();model.dispose()
})
it('removes both caches even if the post-delete list GET fails',async()=>{
 const {model,transport}=setup();await ready(model);await model.loadPersonal(1)
 vi.mocked(transport.list).mockRejectedValueOnce(new ApiError(0,'NETWORK_ERROR','Read offline'))
 expect(await model.remove()).toBe(true);expect(model.state.list.items).toHaveLength(0);expect(model.state.personal.items).toHaveLength(0)
 expect(model.state.success).toContain('笔记已删除');expect(model.state.error).toBe('Read offline');expect(transport.remove).toHaveBeenCalledOnce();model.dispose()
})
it('keeps an unsuccessful unlink visible as a failure without erasing the editor',async()=>{
 const {model,transport}=setup();await ready(model)
 vi.mocked(transport.unlink).mockRejectedValueOnce(new ApiError(403,'INVALID_CSRF_TOKEN','Unlink rejected'))
 expect(await model.unlink()).toBe(false);expect(model.state.editor?.note.id).toBe('note-one')
 expect(model.state.list.items).toHaveLength(1);expect(model.state.success).toBe('');expect(model.state.error).toBe('Unlink rejected');model.dispose()
})
it('invalidates personal-list responses that started before deletion',async()=>{
 const {model,transport,records}=setup();records.get('note-one')!.documents.push({id:'doc-b',title:'Document B'});await ready(model);await model.loadPersonal(1);let finish!:(page:NotesPage)=>void
 vi.mocked(transport.list).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve))
 const oldPersonal=model.loadPersonal(1);await vi.advanceTimersByTimeAsync(0)
 await model.setDocument('doc-b');await model.choose('note-one');expect(await model.remove()).toBe(true)
 finish({items:[base()],page:1,pageSize:20,total:1});await oldPersonal
 expect(model.state.personal.items).toHaveLength(0);expect(model.state.personal.total).toBe(0);model.dispose()
})
it('does not unlink a newly selected note after an awaited autosave',async()=>{
 const {model,transport}=setup();await ready(model);let finish!:(note:NoteDTO)=>void
 vi.mocked(transport.patch).mockImplementationOnce(()=>new Promise(resolve=>finish=resolve))
 model.edit('content','Saving first note');await vi.advanceTimersByTimeAsync(800)
 const selection=model.choose('note-two');await vi.advanceTimersByTimeAsync(0)
 const operation=model.unlink();await vi.advanceTimersByTimeAsync(0)
 vi.mocked(transport.get).mockResolvedValueOnce({...base(),id:'note-two',title:'Second note',content:'Second body'})
 finish({...base(),content:'Saving first note',version:2});expect(await operation).toBe(false);await selection
 expect(transport.unlink).not.toHaveBeenCalled();expect(model.state.editor?.note.id).toBe('note-two');model.dispose()
})

it('clears an earlier unlink notice when a new association attempt fails',async()=>{
 const {model,transport}=setup();await ready(model);expect(await model.unlink()).toBe(true)
 expect(model.state.success).toContain('已从当前文献解除关联')
 vi.mocked(transport.link).mockRejectedValueOnce(new ApiError(403,'LINK_REJECTED','Association failed'))
 expect(await model.link('note-one')).toBe(false)
 expect(model.state.success).toBe('');expect(model.state.error).toBe('Association failed');expect(model.state.list.items).toHaveLength(0);model.dispose()
})

it('keeps the same note and its complete associations when switching associated document tabs',async()=>{
 const {model,transport,records}=setup();records.get('note-one')!.documents.push({id:'doc-b',title:'Document B'});await ready(model)
 const original=clone(records.get('note-one'))
 for(const documentId of ['doc-b','doc-a','doc-b']){
  expect(await model.setDocument(documentId)).toBe(true)
  expect(model.state.editor?.note.id).toBe('note-one');expect(model.state.editor?.content).toBe('Saved content')
  expect(model.state.editor?.note.documents.map(document=>document.id)).toEqual(['doc-a','doc-b'])
 }
 expect(records.get('note-one')).toEqual(original)
 for(const operation of [transport.patch,transport.link,transport.unlink,transport.remove])expect(operation).not.toHaveBeenCalled()
 model.dispose()
})
it('retains the complete selected note while its panel is closed across associated tabs',async()=>{
 const {model,records}=setup();records.get('note-one')!.documents.push({id:'doc-b',title:'Document B'});await ready(model)
 await model.setOpen(false);expect(await model.setDocument('doc-b')).toBe(true)
 expect(model.state.editor?.note.id).toBe('note-one');expect(model.state.editor?.note.documents).toHaveLength(2)
 await model.setOpen(true);expect(model.state.editor?.note.documents.map(document=>document.id)).toEqual(['doc-a','doc-b']);model.dispose()
})
