import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {nextTick} from 'vue'
import TranslationPanel from '../src/components/TranslationPanel.vue'
import {api,ApiError} from '../src/api'
import {publishContext} from '../src/reader/context'
import {clearReaderTabs,openReaderTab} from '../src/reader/state'
import {unreliableTextMessage} from '../src/reader/textQuality'
vi.mock('../src/api',async importOriginal=>({...await importOriginal<typeof import('../src/api')>(),api:vi.fn()}))
let wrapper:VueWrapper
beforeEach(()=>{vi.mocked(api).mockReset();clearReaderTabs();publishContext('context-cleared');wrapper=mount(TranslationPanel,{global:{stubs:{ReaderPanel:{props:['open'],template:'<aside v-if="open"><slot /></aside>'}}}})})
afterEach(()=>{wrapper.unmount();clearReaderTabs();publishContext('context-cleared')})
function select(id='doc-a',text='Optical microscopy',issue?:string,x=.1){publishContext('selection-change',{documentId:id,pageNumber:2,selectedText:text,selectionPosition:[{pageNumber:2,textQuote:text,rects:[{x,y:.1,width:.2,height:.1}]}],textExtractionIssue:issue})}
function respond(normalized?:string){vi.mocked(api).mockImplementation(async(path,options)=>{const body=JSON.parse(String(options?.body));return {originalText:body.text,modelInputText:normalized??body.text,translatedText:'Mock translation',source:{documentId:path.split('/')[2],...body,sourceType:'translation'}}})}
async function open(){(wrapper.vm as unknown as {toggle():void}).toggle();await nextTick()}
async function translate(){(wrapper.vm as unknown as {translate():void}).translate();await flushPromises()}
it('shows a readable title and physical page while preserving the internal document ID',async()=>{openReaderTab('doc-a','Optical study');select();respond();await open();expect(wrapper.get('[data-testid="translation-source"]').text()).toBe('Optical study · PDF 第 2 页');expect(api).not.toHaveBeenCalled();await translate();expect(api).toHaveBeenCalledWith('/documents/doc-a/translations',expect.objectContaining({method:'POST'}),expect.any(String));expect(wrapper.get('[data-testid="translation-result-source"]').text()).toContain('Optical study · PDF 第 2 页');expect(wrapper.text()).not.toContain('doc-a')})
it('uses a stable fallback when the document title is absent',async()=>{openReaderTab('doc-a','  ');select();await open();expect(wrapper.get('[data-testid="translation-source"]').text()).toBe('未命名文献 · PDF 第 2 页');expect(wrapper.text()).not.toContain('doc-a')})
it('document switching and restoration retain the correct result title',async()=>{openReaderTab('doc-a','First study');openReaderTab('doc-b','Second study');select();respond();await translate();select('doc-b','Another passage');await nextTick();expect(wrapper.get('[data-testid="translation-source"]').text()).toBe('Second study · PDF 第 2 页');expect(wrapper.find('[data-testid="translation-result"]').exists()).toBe(false);select();await nextTick();expect(wrapper.get('[data-testid="translation-result-source"]').text()).toContain('First study · PDF 第 2 页');expect(wrapper.text()).not.toContain('Second study')})
it('unreliable mapping appears once and never issues a model request',async()=>{openReaderTab('doc-a','Mapping sample');select('doc-a','unmapped',unreliableTextMessage);await translate();expect(wrapper.findAll('[role="alert"]')).toHaveLength(1);expect(wrapper.get('[role="alert"]').text()).toBe(unreliableTextMessage);expect(wrapper.text().split(unreliableTextMessage)).toHaveLength(2);expect(api).not.toHaveBeenCalled();expect(wrapper.get('button').attributes('disabled')).toBeDefined()})
it('retains raw selection and separately discloses normalized model input',async()=>{openReaderTab('doc-a','Line-ending sample');select('doc-a','disor-\nders');respond('disorders');await translate();expect(wrapper.get('[data-testid="translation-original"]').text()).toBe('disor-\nders');expect(wrapper.get('summary').text()).toBe('已按 PDF 换行证据合并断词');expect(wrapper.get('[data-testid="translation-model-input"]').text()).toBe('disorders');expect(JSON.parse(String(vi.mocked(api).mock.calls[0]![1]?.body)).text).toBe('disor-\nders')})
it('does not show a normalization notice when model input equals the raw source',async()=>{select();respond();await translate();expect(wrapper.find('details').exists()).toBe(false)})

it('clearly separates the previous result from a new selection and reveals its exact source',async()=>{
  openReaderTab('doc-a','Optical study');select();respond();await translate()
  expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('当前选区译文')
  select('doc-a','A different passage');await nextTick()
  expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('上一条译文')
  expect(wrapper.get('[data-testid="translation-result-original"]').text()).toBe('Optical microscopy')
  expect(wrapper.get('[data-testid="translation-original"]').text()).toBe('A different passage')
  expect(wrapper.get('[data-testid="translation-result-source"]').text()).toBe('Optical study · PDF 第 2 页 · 英译中')
  expect(wrapper.text()).not.toContain('此译文来源')
  expect(wrapper.text()).not.toContain('当前显示的是上次成功结果')
})
it('the same words at a different PDF position are not labelled as the current result',async()=>{
  select();respond();await translate();select('doc-a','Optical microscopy',undefined,.4);await nextTick()
  expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('上一条译文')
  expect(wrapper.get('[data-testid="translation-result-original"]').text()).toBe('Optical microscopy')
})
it('changing direction retains the previous result with its original direction',async()=>{
  select();respond();await translate()
  await wrapper.get('select[aria-label="语言方向"]').setValue('zh-en')
  expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('上一条译文')
  expect(wrapper.get('[data-testid="translation-result-source"]').text()).toContain('英译中')
  expect(api).toHaveBeenCalledTimes(1)
})
it('disables duplicate manual actions while a request is in flight and exposes toolbar busy',async()=>{
  let finish!:()=>void
  vi.mocked(api).mockImplementation(async(path,options)=>{
    const body=JSON.parse(String(options?.body))
    return new Promise(resolve=>{finish=()=>resolve({originalText:body.text,translatedText:'Mock delayed translation',source:{documentId:path.split('/')[2],...body,sourceType:'translation'}})})
  })
  select();await translate()
  expect(wrapper.get('button').text()).toBe('翻译中…')
  expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  expect((wrapper.vm as unknown as {busy:boolean}).busy).toBe(true)
  await wrapper.get('button').trigger('click');expect(api).toHaveBeenCalledTimes(1)
  finish();await flushPromises()
  expect(wrapper.get('button').text()).toBe('翻译')
  expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  expect((wrapper.vm as unknown as {busy:boolean}).busy).toBe(false)
})

it('shows the automatic pause once after a rate limit and keeps explicit retry available',async()=>{
  vi.mocked(api).mockRejectedValueOnce(new ApiError(429,'MODEL_QUOTA','模型服务已限流，请稍后重试'))
  select();await open();await wrapper.get('select[aria-label="翻译模式"]').setValue('realtime');await translate()
  expect(api).toHaveBeenCalledTimes(1)
  expect(wrapper.get('[role="alert"]').text()).toContain('模型服务已限流')
  expect(wrapper.findAll('[data-testid="translation-auto-paused"]')).toHaveLength(1)
  expect(wrapper.get('[data-testid="translation-auto-paused"]').text()).toBe('实时翻译已暂停，请稍后手动重试。')
  const retry=wrapper.findAll('button').find(button=>button.text()==='重试翻译')!
  expect(retry.attributes('disabled')).toBeUndefined()
  respond();await retry.trigger('click');await flushPromises()
  expect(api).toHaveBeenCalledTimes(2)
  expect(wrapper.find('[data-testid="translation-auto-paused"]').exists()).toBe(false)
})

it('saves a signed matching result as current and preserves its frozen source when selection changes',async()=>{
 select();respond();await translate()
 const original=JSON.parse(String(vi.mocked(api).mock.calls[0]![1]?.body))
 vi.mocked(api).mockResolvedValueOnce({originalText:original.text,translatedText:'Signed Mock',source:{documentId:'doc-a',...original,sourceType:'translation'},
  translationProof:{version:1,issuedAt:123,signature:'a'.repeat(64),provenance:'isolated_mock'}})
 await translate()
 const save=wrapper.findAll('button').find(button=>button.text()==='保存到笔记')!
 expect(save.attributes('disabled')).toBeUndefined()
 await save.trigger('click')
 const emitted=wrapper.emitted('save-to-note')!
 expect(emitted[0]![0]).toMatchObject({source:{documentId:'doc-a',pageNumber:2,originalText:'Optical microscopy',historical:false,translationProof:{provenance:'isolated_mock'}}})
 expect(wrapper.get('[data-testid="translation-mock-label"]').text()).toContain('非真实模型')
 select('doc-a','Different passage');await nextTick();await save.trigger('click')
 expect(emitted[0]![0]).toMatchObject({source:{originalText:'Optical microscopy',historical:false}})
 expect(wrapper.emitted('save-to-note')![1]![0]).toMatchObject({source:{originalText:'Optical microscopy',historical:true,confirmHistorical:false}})
})
it('requires a real current PDF selection for current-result saving even after the panel remembers the previous source',async()=>{
 select();respond();await translate()
 const original=JSON.parse(String(vi.mocked(api).mock.calls[0]![1]?.body))
 vi.mocked(api).mockResolvedValueOnce({originalText:original.text,translatedText:'Signed Mock',source:{documentId:'doc-a',...original,sourceType:'translation'},
  translationProof:{version:1,issuedAt:123,signature:'a'.repeat(64),provenance:'isolated_mock'}})
 await translate()
 publishContext('selection-change',{documentId:'doc-a',pageNumber:2,selectedText:'',selectionPosition:null})
 await nextTick()
 expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('上一条译文')
 await wrapper.findAll('button').find(button=>button.text()==='保存到笔记')!.trigger('click')
 expect(wrapper.emitted('save-to-note')![0]![0]).toMatchObject({source:{historical:true,documentId:'doc-a',pageNumber:2}})
})
it('displays old P2 responses but cannot save an unsigned result as a trusted translation',async()=>{
 select();respond();await translate()
 const save=wrapper.findAll('button').find(button=>button.text()==='保存到笔记')!
 expect(save.attributes('disabled')).toBeDefined()
 expect(wrapper.text()).toContain('没有可验证的来源回执')
 expect(wrapper.emitted('save-to-note')).toBeUndefined()
})
