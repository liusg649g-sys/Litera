import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {pdfNoteCapture} from '../src/reader/noteCapture'
import {createNotesController,type NoteDTO,type NotesApi} from '../src/notes'
import type {ReaderContext} from '../src/reader/context'

const context=():ReaderContext=>({documentId:'doc-a',pageNumber:9,selectedText:'  Original\ntext  ',selectionPosition:[{pageNumber:3,textQuote:'Original\ntext',rects:[{x:.1,y:.1,width:.2,height:.1}]}],contextRevision:7,annotationId:null})
it('freezes raw PDF text and physical source positions without changing the shared reader context',()=>{
 const reader=context(),original=JSON.stringify(reader),result=pdfNoteCapture(reader,'Source title','doc-a')
 expect(result.draft?.source.originalText).toBe('  Original\ntext  ')
 expect(result.draft?.source.pageNumber).toBe(3)
 expect(result.draft?.source.positions).not.toBe(reader.selectionPosition)
 expect(JSON.stringify(reader)).toBe(original)
 reader.selectionPosition![0]!.textQuote='changed'
 expect(result.draft?.source.positions[0]!.textQuote).toBe('Original\ntext')
})
it('rejects text in ordinary inputs, empty selections, and another document',()=>{
 expect(pdfNoteCapture({...context(),selectionPosition:null},'Title','doc-a').draft).toBeNull()
 expect(pdfNoteCapture(context(),'Title','doc-b').draft).toBeNull()
 expect(pdfNoteCapture(null,'Title','doc-a').draft).toBeNull()
})
it('retains the existing mapping guard and length limit rather than laundering unreliable characters',()=>{
 expect(pdfNoteCapture({...context(),textExtractionIssue:'字体映射不可靠'},'Title','doc-a').error).toBe('字体映射不可靠')
 expect(pdfNoteCapture({...context(),selectedText:'\uF031'},'Title','doc-a').draft).toBeNull()
 expect(pdfNoteCapture({...context(),selectedText:'a'.repeat(6001)},'Title','doc-a').error).toContain('6000')
})
const note=():NoteDTO=>({id:'note-a',title:'Notebook',content:'Personal body',version:1,contentFormat:'plain-text',sourceSchemaVersion:1,sources:[],documents:[{id:'doc-a',title:'A'}],createdAt:'2026-10-23',updatedAt:'2026-10-23'})
function setup(){
 let current=note()
 const transport:NotesApi={
 config:vi.fn().mockResolvedValue({available:true,titleMaxLength:200,contentMaxLength:100000,contentFormat:'plain-text'}),
 list:vi.fn().mockImplementation(async()=>({items:[current],total:1,page:1,pageSize:20})),
  search:vi.fn().mockResolvedValue({items:[],query:'',total:0,page:1,pageSize:20}),
 get:vi.fn().mockImplementation(async()=>current),
 patch:vi.fn().mockImplementation(async(_id,input)=>{current={...current,...input,version:input.version+1};return current}),
 create:vi.fn(),link:vi.fn(),unlink:vi.fn(),remove:vi.fn(),
 }
 const model=createNotesController(transport,sessionStorage)
 return {model,transport,set:(value:NoteDTO)=>{current=value}}
}
beforeEach(()=>{sessionStorage.clear();vi.useFakeTimers()})
afterEach(()=>{vi.clearAllTimers();vi.useRealTimers()})
async function ready(model:ReturnType<typeof createNotesController>){await model.setUser('user-a');await model.setDocument('doc-a');await model.setOpen(true);await model.choose('note-a')}
it('installs a committed source block and uses its version for later body autosave',async()=>{
 const {model,transport,set}=setup();await ready(model)
 const committed={...note(),version:2,sources:[{id:'block-a',originalText:'Original'}]}
 set(committed);expect(await model.acceptCapture(committed)).toBe(true)
 expect(model.state.editor?.note.sources).toEqual(committed.sources)
 model.edit('content','New thoughts');await model.flush()
 expect(transport.patch).toHaveBeenCalledWith('note-a',{version:2,title:'Notebook',content:'New thoughts'})
 expect(model.state.editor?.note.sources).toEqual(committed.sources)
 model.dispose()
})
it('never overwrites a dirty editor with a capture response',async()=>{
 const {model}=setup();await ready(model);model.edit('content','Unsaved body')
 expect(await model.acceptCapture({...note(),version:2,sources:[{id:'block'}]})).toBe(false)
 expect(model.state.editor?.content).toBe('Unsaved body')
 model.dispose()
})
it('renders a captured unassociated personal note without silently adding document membership',async()=>{
 const {model}=setup();await ready(model)
 const personal={...note(),id:'personal-note',documents:[{id:'doc-b',title:'B'}],sources:[{id:'block-a'}]}
 expect(await model.acceptCapture(personal)).toBe(true)
 expect(model.state.editor?.note.documents).toEqual(personal.documents)
 expect(model.state.success).toContain('未关联当前文献')
 expect(model.state.open).toBe(true)
 model.dispose()
})
