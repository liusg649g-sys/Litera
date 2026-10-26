import { reactive } from 'vue'
import { api, ApiError } from './api'
import { auth } from './auth'

export interface NoteDocument { id: string; title: string }
export interface NoteSummary { id: string; title: string; contentFormat: 'plain-text'; version: number; sourceSchemaVersion: number; createdAt: string; updatedAt: string; documents: NoteDocument[] }
export interface NoteDTO extends NoteSummary { content: string; sources: unknown[] }
export interface NotesPage { items: NoteSummary[]; page: number; pageSize: number; total: number }
export type NoteSearchField = 'title' | 'content' | 'source_original' | 'source_translation' | 'ai_question' | 'ai_answer'
export interface NoteSearchMatch { field: NoteSearchField; label: string; snippet: string; matchStart: number; matchEnd: number; leadingEllipsis: boolean; trailingEllipsis: boolean; sourceBlockId?: string; documentId?: string; pageNumber?: number }
export interface NoteSearchResult extends NoteSummary { matches: NoteSearchMatch[] }
export interface NoteSearchPage { items: NoteSearchResult[]; query: string; page: number; pageSize: number; total: number }
export interface NotesConfig { available: boolean; contentMaxLength: number; titleMaxLength: number; contentFormat: 'plain-text' }
export interface NotesApi {
  config(): Promise<NotesConfig>
  list(documentId: string | null, page: number): Promise<NotesPage>
  search(query: string, page: number): Promise<NoteSearchPage>
  get(id: string): Promise<NoteDTO>
  create(input: {id: string; title: string; content: string; documentId: string}): Promise<NoteDTO>
  patch(id: string, input: {version: number; title: string; content: string}): Promise<NoteDTO>
  link(id: string, documentId: string): Promise<NoteDTO>
  unlink(id: string, documentId: string): Promise<NoteDTO>
  remove(id: string, version: number): Promise<void>
}
const notePath = (id: string) => '/notes/' + encodeURIComponent(id)
export const notesApi: NotesApi = {
  config: () => api('/notes/config'),
  list: (documentId,page) => api(`/notes?page=${page}&pageSize=20${documentId ? '&documentId='+encodeURIComponent(documentId) : ''}`),
  search: (query,page) => api(`/notes/search?q=${encodeURIComponent(query)}&page=${page}&pageSize=20`),
  get: id => api(notePath(id)),
  create: body => api('/notes',{method:'POST',body:JSON.stringify(body)},auth.csrfToken),
  patch: (id,body) => api(notePath(id),{method:'PATCH',body:JSON.stringify(body)},auth.csrfToken),
  link: (id,documentId) => api(`${notePath(id)}/documents/${encodeURIComponent(documentId)}`,{method:'PUT'},auth.csrfToken),
  unlink: (id,documentId) => api(`${notePath(id)}/documents/${encodeURIComponent(documentId)}`,{method:'DELETE'},auth.csrfToken),
  remove: (id,version) => api(`${notePath(id)}?version=${version}`,{method:'DELETE'},auth.csrfToken),
}
interface Editor { note: NoteDTO; title: string; content: string; dirty: boolean; saving: boolean; error: string; conflict: boolean }
interface Draft { schema: 1; userId: string; noteId: string; version: number; title: string; content: string }
const emptyPage = (): NotesPage => ({items:[],page:1,pageSize:20,total:0})
const emptySearch = (): NoteSearchPage => ({items:[],query:'',page:1,pageSize:20,total:0})
const message = (error: unknown) => error instanceof Error ? error.message : '笔记操作失败，请重试。'
export function createNotesController(transport: NotesApi = notesApi, storage?: Storage, delay = 800, searchDelay = 350) {
  const state = reactive({open:false,userId:'',documentId:'',checking:false,available:false,unavailable:'',config:{available:false,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'} as NotesConfig,
    list:emptyPage(),personal:emptyPage(),search:{...emptySearch(),input:'',loading:false,error:''},chooser:false,loading:false,busy:false,error:'',success:'',backupWarning:'',editor:null as Editor | null})
  let epoch=0, context=0, selection=0, documentChange=0, listRead=0, personalRead=0, searchRead=0, timer:ReturnType<typeof setTimeout> | undefined, searchTimer:ReturnType<typeof setTimeout> | undefined, activeSave:Promise<void>|null=null, mutation:Promise<unknown>|null=null
  let pendingCreate:{id:string;title:string;content:string;documentId:string}|null=null
  const selected=new Map<string,string>()
  const draftKey=(id:string,user=state.userId)=>`litera:notes-draft:${user}:${id}`
  function stash(editor: Editor) {
    if(!editor.dirty || !state.userId)return
    if(!storage){state.backupWarning='浏览器无法保留本地草稿；保存成功前请不要刷新或关闭页面。';return}
    const value:Draft={schema:1,userId:state.userId,noteId:editor.note.id,version:editor.note.version,title:editor.title,content:editor.content}
    try{storage.setItem(draftKey(editor.note.id),JSON.stringify(value));state.backupWarning=''}catch{state.backupWarning='浏览器无法保留本地草稿；保存成功前请不要刷新或关闭页面。'}
  }
  function clearDraft(id:string){try{storage?.removeItem(draftKey(id))}catch{/* A failed cleanup must not turn a server save into a failure. */}}
  function install(note:NoteDTO,restore=true) {
    const editor:Editor={note,title:note.title,content:note.content,dirty:false,saving:false,error:'',conflict:false}
    if(restore && storage)try{
      const raw=storage.getItem(draftKey(note.id)),draft:Draft|null=raw?JSON.parse(raw):null
      if(draft?.schema===1 && draft.userId===state.userId && draft.noteId===note.id && typeof draft.title==='string' && typeof draft.content==='string' && Number.isInteger(draft.version) && draft.title.length<=state.config.titleMaxLength && draft.content.length<=state.config.contentMaxLength){
        editor.title=draft.title;editor.content=draft.content;editor.dirty=editor.title!==note.title || editor.content!==note.content
        if(editor.dirty){editor.note={...note,version:draft.version};editor.conflict=draft.version!==note.version;editor.error=editor.conflict?'服务器版本已变化，本地草稿已保留；请确认后载入服务器版本。':''}
        else clearDraft(note.id)
      }
    }catch{state.backupWarning='本地草稿无法读取，未覆盖服务器内容。'}
    state.success='';state.editor=editor;selected.set(state.documentId,note.id)
    if(editor.dirty && !editor.conflict)schedule()
  }
  function updateSummary(note:NoteDTO){
    for(const page of [state.list,state.personal]){const index=page.items.findIndex(item=>item.id===note.id);if(index>=0)page.items[index]=note}
    const index=state.search.items.findIndex(item=>item.id===note.id)
    if(index>=0)state.search.items[index]={...note,matches:state.search.items[index]!.matches}
  }
  function invalidateReads(){listRead++;personalRead++;selection++;state.loading=false}
  function removeCached(page:NotesPage,id:string){if(page.items.some(note=>note.id===id)){page.items=page.items.filter(note=>note.id!==id);page.total=Math.max(0,page.total-1)}}
  function schedule(){clearTimeout(timer);if(state.editor?.dirty && !state.editor.error && !state.editor.conflict)timer=setTimeout(()=>{void flush()},delay)}
  function edit(field:'title'|'content',value:string){const editor=state.editor;if(!editor || state.busy)return;editor[field]=value;editor.dirty=editor.title!==editor.note.title || editor.content!==editor.note.content;stash(editor);if(!editor.dirty){clearDraft(editor.note.id);editor.error='';editor.conflict=false}schedule()}
  async function saveOne(editor:Editor,scope:number){
    const snapshot={version:editor.note.version,title:editor.title.trim() || '未命名笔记',content:editor.content}
    editor.saving=true
    let job!:Promise<void>
    job=(async()=>{try{
      const result=await Promise.resolve().then(()=>transport.patch(editor.note.id,snapshot))
      if(scope!==epoch || state.editor!==editor)return
      const unchanged=(editor.title.trim() || '未命名笔记')===snapshot.title && editor.content===snapshot.content
      editor.note=result;updateSummary(result)
      if(unchanged){editor.title=result.title;editor.content=result.content;editor.dirty=false;editor.error='';clearDraft(result.id)}else{editor.dirty=true;stash(editor)}
    }catch(error){if(scope===epoch && state.editor===editor){editor.error=message(error);editor.conflict=error instanceof ApiError && error.status===409;stash(editor)}}
    finally{if(scope===epoch)editor.saving=false;if(activeSave===job)activeSave=null}})()
    activeSave=job;await job
  }
  async function flush():Promise<boolean>{
    clearTimeout(timer);const scope=epoch
    if(mutation)await mutation.catch(()=>undefined)
    while(scope===epoch && state.editor?.dirty){
      if(state.editor.error || state.editor.conflict)return false
      if(activeSave)await activeSave;else await saveOne(state.editor,scope)
    }
    return scope===epoch && !pendingCreate && !state.editor?.dirty
  }
  async function retrySave(){if(state.editor?.conflict)return false;if(state.editor)state.editor.error='';return flush()}
  async function refreshList(page=state.list.page){const scope=epoch,token=context,request=++listRead,documentId=state.documentId;if(!state.available || !documentId)return
    state.loading=true;state.error=''
    try{const value=await transport.list(documentId,page);if(scope===epoch && token===context && request===listRead)state.list=value}catch(error){if(scope===epoch && token===context && request===listRead)state.error=message(error)}finally{if(scope===epoch && token===context && request===listRead)state.loading=false}}
  async function loadPersonal(page=state.personal.page){if(!state.available)return;const scope=epoch,request=++personalRead;state.busy=true;state.error=''
    try{const value=await transport.list(null,page);if(scope===epoch && request===personalRead)state.personal=value}catch(error){if(scope===epoch && request===personalRead)state.error=message(error)}finally{if(scope===epoch && request===personalRead)state.busy=false}}
  function clearSearch(){
    clearTimeout(searchTimer);searchRead++;Object.assign(state.search,emptySearch(),{input:'',loading:false,error:''})
  }
  async function runSearch(page=1,query=state.search.input.trim()){
    clearTimeout(searchTimer);const scope=epoch,request=++searchRead
    if(!state.available || !query){if(!query)Object.assign(state.search,emptySearch(),{input:state.search.input,loading:false,error:''});return false}
    state.search.loading=true;state.search.error='';state.search.page=page
    try{
      const value=await transport.search(query,page)
      if(scope!==epoch || request!==searchRead || state.search.input.trim()!==query)return false
      Object.assign(state.search,value,{input:state.search.input,loading:false,error:''});return true
    }catch(error){
      if(scope===epoch && request===searchRead && state.search.input.trim()===query){state.search.loading=false;state.search.error=message(error)}
      return false
    }
  }
  function setSearchInput(value:string){
    state.search.input=value;clearTimeout(searchTimer);searchRead++;state.search.error=''
    const query=value.trim()
    if(!query){Object.assign(state.search,emptySearch(),{input:value,loading:false,error:''});return}
    state.search.items=[];state.search.total=0;state.search.page=1;state.search.query='';state.search.loading=true
    const scope=epoch
    searchTimer=setTimeout(()=>{if(scope===epoch)void runSearch(1,query)},searchDelay)
  }
  async function choose(id:string){const request=++selection;if(!await flush() || request!==selection)return false;const scope=epoch,token=context;state.busy=true;state.error='';state.success=''
    try{const value=await transport.get(id);if(scope!==epoch || token!==context || request!==selection)return false;install(value);return true}catch(error){if(scope===epoch && token===context && request===selection)state.error=message(error);return false}finally{if(scope===epoch && token===context && request===selection)state.busy=false}}
  async function setDocument(id:string){
    const request=++documentChange,scope=epoch
    if(state.documentId===id)return true
    if(!await flush() || request!==documentChange || scope!==epoch)return false
    // Association membership comes from the complete server DTO, never the active tab.
    const carried=state.editor?.note.documents.some(document=>document.id===id)?state.editor:null
    const token=++context;invalidateReads();state.documentId=id;state.busy=false;state.editor=carried;state.list=emptyPage();state.error='';state.success=''
    if(carried)selected.set(id,carried.note.id)
    if(state.open && state.available){
      await refreshList(1)
      if(scope!==epoch || token!==context || request!==documentChange)return false
      const previous=carried?.note.id || selected.get(id)
      if(previous && (carried || state.list.items.some(note=>note.id===previous)))await choose(previous)
    }
    return true
  }
  async function setUser(id:string){
    clearTimeout(timer);clearTimeout(searchTimer);epoch++;context++;documentChange++;searchRead++;invalidateReads();const scope=epoch
    state.userId=id;state.open=false;state.editor=null;state.list=emptyPage();state.personal=emptyPage();Object.assign(state.search,emptySearch(),{input:'',loading:false,error:''});state.chooser=false;state.error='';state.success='';state.backupWarning='';state.available=false;state.checking=!!id;state.unavailable='';state.loading=false;state.busy=false;selected.clear();pendingCreate=null;mutation=null;activeSave=null
    if(!id)return
    try{const value=await transport.config();if(scope!==epoch)return;state.config=value;state.available=value.available;if(!value.available)state.unavailable='笔记尚未部署，等待数据库升级确认。';else if(state.open && state.documentId)await refreshList(1)}catch(error){if(scope!==epoch)return;state.unavailable=error instanceof ApiError && error.status===404?'笔记尚未部署，等待数据库升级确认。':message(error)}finally{if(scope===epoch)state.checking=false}
  }
  async function setOpen(value:boolean){state.open=value;if(value && state.available && !state.list.items.length)await refreshList(1)}
  async function create(){if(!state.available || !state.documentId || state.busy)return false;if(!await flush() && (!pendingCreate || state.editor?.dirty))return false
    const scope=epoch,documentId=state.documentId;pendingCreate??={id:crypto.randomUUID(),title:'未命名笔记',content:'',documentId};state.busy=true;state.error='';state.success=''
    const work=(async()=>{try{const value=await transport.create(pendingCreate!);if(scope!==epoch)return false;pendingCreate=null;await refreshList(1);if(state.documentId===documentId)install(value,false);return true}catch(error){if(scope===epoch)state.error=message(error);return false}finally{if(scope===epoch)state.busy=false}})();mutation=work;const result=await work;if(mutation===work)mutation=null;return result}
  async function link(id:string){if(state.busy || !state.available || !await flush())return false;const scope=epoch,documentId=state.documentId;state.busy=true;state.error='';state.success=''
    const work=(async()=>{try{const value=await transport.link(id,documentId);if(scope!==epoch)return false;await refreshList(1);state.chooser=false;install(value);return true}catch(error){if(scope===epoch)state.error=message(error);return false}finally{if(scope===epoch)state.busy=false}})();mutation=work;const result=await work;if(mutation===work)mutation=null;return result}
  async function unlink(){
    const editor=state.editor,scope=epoch,token=context,documentId=state.documentId
    if(!editor || state.busy || !await flush() || scope!==epoch || token!==context || state.editor!==editor || state.busy)return false
    const id=editor.note.id;state.busy=true;state.error='';state.success='';invalidateReads()
    const work=(async()=>{try{
      const result=await transport.unlink(id,documentId)
      if(scope!==epoch || token!==context)return false
      invalidateReads();updateSummary(result);removeCached(state.list,id);state.editor=null;selected.delete(documentId)
      state.success='已从当前文献解除关联。笔记已保留'+(result.documents.length?'，仍关联：'+result.documents.map(document=>document.title || '未命名文献').join('、')+'。':'，可从个人已有笔记重新关联。')
      await refreshList(1);return true
    }catch(error){if(scope===epoch && token===context)state.error=message(error);return false}finally{if(scope===epoch && token===context)state.busy=false}})()
    mutation=work;const result=await work;if(mutation===work)mutation=null;return result
  }
  async function remove(){
    const editor=state.editor,scope=epoch,token=context
    if(!editor || state.busy || !await flush() || scope!==epoch || token!==context || state.editor!==editor || state.busy)return false
    const note=editor.note;state.busy=true;state.error='';state.success='';invalidateReads()
    const work=(async()=>{try{
      await transport.remove(note.id,note.version)
      if(scope!==epoch || token!==context)return false
      invalidateReads();removeCached(state.list,note.id);removeCached(state.personal,note.id);if(state.search.items.some(item=>item.id===note.id)){state.search.items=state.search.items.filter(item=>item.id!==note.id);state.search.total=Math.max(0,state.search.total-1)}clearDraft(note.id);state.editor=null
      for(const [doc,id]of selected)if(id===note.id)selected.delete(doc)
      state.success='笔记已删除，全部文献关联已移除。'
      await refreshList(1);return true
    }catch(error){if(scope===epoch && token===context)state.error=message(error);return false}finally{if(scope===epoch && token===context)state.busy=false}})()
    mutation=work;const result=await work;if(mutation===work)mutation=null;return result
  }
  async function reload(){if(!state.editor || state.busy)return false;const scope=epoch,id=state.editor.note.id;state.busy=true;state.error='';clearTimeout(timer)
    try{const value=await transport.get(id);if(scope!==epoch)return false;clearDraft(id);install(value,false);return true}catch(error){if(scope===epoch)state.error=message(error);return false}finally{if(scope===epoch)state.busy=false}}
  async function acceptCapture(note:NoteDTO){
    // Called only after the modal's frozen operation succeeds. Never overwrite a draft.
    if(!state.available || state.busy || state.editor?.dirty || state.editor?.saving || pendingCreate)return false
    const scope=epoch,token=context
    invalidateReads();updateSummary(note);install(note,false);state.open=true
    state.success='已保存到笔记。'+(!note.documents.some(document=>document.id===state.documentId)?'此笔记未关联当前文献，来源已保留；可从个人笔记再次选择。':'')
    await refreshList(1)
    return scope===epoch && token===context
  }
  function dispose(){clearTimeout(timer);clearTimeout(searchTimer);epoch++;context++;documentChange++;searchRead++;invalidateReads();state.open=false;state.editor=null;state.userId='';state.available=false;state.busy=false;state.loading=false;selected.clear();pendingCreate=null;mutation=null;activeSave=null}
  return {state,setUser,setDocument,setOpen,refreshList,loadPersonal,setSearchInput,runSearch,clearSearch,choose,create,edit,flush,retrySave,link,unlink,remove,reload,dispose,
    acceptCapture,
    hasUnsaved:()=>!!(pendingCreate || state.editor?.dirty || state.editor?.saving),
    beforeLeave:()=>flush(),
  }
}
