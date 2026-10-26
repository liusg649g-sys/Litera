import { expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import NoteSourceBlocks from '../src/components/NoteSourceBlocks.vue'
import type { StoredSourceBlock } from '../src/notes/captures'
const block=():StoredSourceBlock=>({id:'block-a',kind:'translation_excerpt',createdAt:'2026-10-23',originalText:'<img src=x onerror=alert(1)>',translatedText:'隔离 Mock 译文',sourceLanguage:'en',targetLanguage:'zh',source:{documentId:'doc-a',title:'Original full document title',fileSha256:'a'.repeat(64),pageNumber:3,pageNumbers:[3,4],positions:[],contextRevision:1,precision:'page'},translationProvenance:'isolated_mock',historical:true,requestFingerprint:'fingerprint'})
it('renders safe source snapshots with Mock/history badges and stable metadata',()=>{
 const wrapper=mount(NoteSourceBlocks,{props:{sources:[block()],documents:[{id:'doc-b',title:'Other document'}]}})
 expect(wrapper.get('[aria-label="笔记来源摘录"]').text()).toContain('来源摘录（1）')
 expect(wrapper.text()).toContain('Original full document title · PDF 第 3、4 页')
 expect(wrapper.text()).toContain('来源文献当前未关联')
 expect(wrapper.text()).toContain('隔离 Mock 译文（非真实模型）')
 expect(wrapper.text()).toContain('历史译文快照')
 expect(wrapper.get('[data-source-block-id="block-a"]').attributes('data-source-document-id')).toBe('doc-a')
 expect(wrapper.find('img').exists()).toBe(false)
 expect(wrapper.get('blockquote').text()).toContain('<img')
 wrapper.unmount()
})
it('changing associated documents only changes link status and never source metadata',async()=>{
 const wrapper=mount(NoteSourceBlocks,{props:{sources:[block()],documents:[{id:'doc-a',title:'Renamed current title'}]}})
 expect(wrapper.text()).not.toContain('来源文献当前未关联')
 await wrapper.setProps({documents:[]})
 expect(wrapper.text()).toContain('来源文献当前未关联')
 expect(wrapper.text()).toContain('Original full document title')
 expect(wrapper.text()).not.toContain('Renamed current title')
 expect(wrapper.get('blockquote').text()).toBe(block().originalText)
 wrapper.unmount()
})
it('preserves unknown schemas visibly without rendering arbitrary object payloads',()=>{
 const wrapper=mount(NoteSourceBlocks,{props:{sources:[{kind:'future_kind',private:'do not render'}],documents:[]}})
 expect(wrapper.text()).toContain('当前版本无法识别')
 expect(wrapper.text()).not.toContain('do not render')
 expect(wrapper.findAll('[data-testid="note-source-block"]')).toHaveLength(0)
 wrapper.unmount()
})
it('does not label a legacy translation as verified model output',()=>{
 const record=block();delete record.translationProvenance;record.historical=false
 const wrapper=mount(NoteSourceBlocks,{props:{sources:[record],documents:[]}})
 expect(wrapper.text()).toContain('译文来源尚未验证')
 expect(wrapper.text()).not.toContain('模型译文')
 wrapper.unmount()
})

it('emits its immutable source snapshot and disables navigation without a valid PDF hash',async()=>{
 const value=block(),wrapper=mount(NoteSourceBlocks,{props:{sources:[value],documents:[]}})
 await wrapper.get('button[aria-label="查看原文：Original full document title，PDF 第 3 页"]').trigger('click')
 expect(wrapper.emitted('navigate-source')?.[0]?.[0]).toEqual(value)
 const legacy=block();legacy.source={...legacy.source,fileSha256:''}
 await wrapper.setProps({sources:[legacy]})
 const button=wrapper.get('button[aria-label="查看原文：Original full document title，PDF 第 3 页"]')
 expect(button.attributes()).toHaveProperty('disabled')
 expect(wrapper.text()).toContain('无法可靠定位来源')
 wrapper.unmount()
})