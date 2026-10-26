import {afterEach,beforeEach,expect,it,vi} from 'vitest'
import {mount,flushPromises,type VueWrapper} from '@vue/test-utils'
import {nextTick} from 'vue'
import TranslationPanel from '../src/components/TranslationPanel.vue'
import {auth} from '../src/auth'
import {api} from '../src/api'
import {publishContext} from '../src/reader/context'
vi.mock('../src/api',async original=>({...await original<typeof import('../src/api')>(),api:vi.fn()}))
let wrapper:VueWrapper
const profile={provider:'openai_compatible',baseUrl:'https://model.example.com/v1',model:'Controlled test model',hasApiKey:true,verified:true,revision:'current-revision'}
const options={mockEnabled:true,userEnabled:true,developerEnabled:false,defaultSource:'mock',unifiedAcceptance:true}
function mountPanel(){wrapper=mount(TranslationPanel,{global:{stubs:{RouterLink:{template:'<a><slot /></a>'},ReaderPanel:{props:['open'],template:'<aside v-if="open"><slot /></aside>'}}}})}
function select(){publishContext('selection-change',{documentId:'doc',pageNumber:1,selectedText:'Public test',selectionPosition:[{pageNumber:1,textQuote:'Public test',rects:[{x:.1,y:.1,width:.2,height:.1}]}]})}
function open(){(wrapper.vm as unknown as {toggle():void}).toggle();return nextTick()}
beforeEach(()=>{
 sessionStorage.clear();vi.mocked(api).mockReset();auth.user={id:'owner-a',email:'synthetic@example.com',displayName:'Test',createdAt:'2026-10-26'}
 vi.mocked(api).mockImplementation(async(path,init)=>{
  if(path==='/user-model')return {available:true,profile}
  if(path==='/user-model/options')return options
  const data=JSON.parse(String(init?.body))
  return {originalText:data.text,translatedText:'Controlled Mock response',modelConfiguration:{source:data.modelSource,revision:data.modelRevision},source:{...data,documentId:'doc',sourceType:'translation'},translationProof:{version:1,issuedAt:1,signature:'a'.repeat(64),provenance:data.modelSource==='mock'?'isolated_mock':'model_api'}}
 })
 mountPanel()
})
afterEach(()=>{wrapper.unmount();auth.user=null;publishContext('context-cleared');sessionStorage.clear()})
it('defaults to explicit offline Mock and cannot send a request just by loading or choosing a model',async()=>{
 await flushPromises();select();await open()
 expect((wrapper.get('select[aria-label="翻译模型"]').element as HTMLSelectElement).value).toBe('mock')
 expect(wrapper.find('option[value="developer"]').exists()).toBe(false)
 await wrapper.get('select[aria-label="翻译模型"]').setValue('user');await flushPromises()
 expect(vi.mocked(api).mock.calls.filter(([,init])=>init?.method==='POST')).toHaveLength(0)
 expect(wrapper.get('[data-testid="active-model"]').text()).toContain('Controlled test model')
 ;(wrapper.vm as unknown as {translate():void}).translate();await flushPromises()
 expect(vi.mocked(api).mock.calls.find(([,init])=>init?.method==='POST')?.[1]?.body).toContain('current-revision')
 expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('当前选区译文')
 expect(wrapper.find('[data-testid="translation-mock-label"]').exists()).toBe(false)
})
it('keeps personal choice across remounting but not across user identities',async()=>{
 await flushPromises();await open();await wrapper.get('select[aria-label="翻译模型"]').setValue('user')
 wrapper.unmount();mountPanel();await flushPromises();await open()
 expect((wrapper.get('select[aria-label="翻译模型"]').element as HTMLSelectElement).value).toBe('user')
 auth.user={...auth.user!,id:'owner-b'};await flushPromises();await open()
 expect((wrapper.get('select[aria-label="翻译模型"]').element as HTMLSelectElement).value).toBe('mock')
 expect(sessionStorage.getItem('litera:translation-model:owner-a')).toBe('user')
 expect([...Array(sessionStorage.length)].map((_,i)=>sessionStorage.key(i))).toEqual(['litera:translation-model:owner-a'])
})
it('retains and labels Mock results when switching explicitly to a personal model',async()=>{
 await flushPromises();select();await open();(wrapper.vm as unknown as {translate():void}).translate();await flushPromises()
 expect(wrapper.get('[data-testid="translation-mock-label"]').text()).toContain('非真实模型')
 await wrapper.get('select[aria-label="翻译模型"]').setValue('user')
 expect(wrapper.get('[data-testid="translation-result-state"]').text()).toBe('上一条译文')
 expect(wrapper.get('[data-testid="translation-mock-label"]').text()).toContain('非真实模型')
})
