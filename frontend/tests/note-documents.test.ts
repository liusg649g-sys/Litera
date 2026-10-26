import {afterEach,it,expect} from 'vitest'
import {mount,type VueWrapper} from '@vue/test-utils'
import NoteDocuments from '../src/components/NoteDocuments.vue'
import type {NoteDocument} from '../src/notes'
let wrapper:VueWrapper|undefined
const documents=():NoteDocument[]=>[{id:'doc-a',title:'Document A'},{id:'doc-b',title:'Document B'}]
afterEach(()=>{wrapper?.unmount();wrapper=undefined})

it('shows every association including the current document with a count and separate rows',()=>{
 wrapper=mount(NoteDocuments,{props:{documents:documents(),currentDocumentId:'doc-a'}})
 expect(wrapper.get('section').attributes('aria-label')).toBe('关联文献')
 expect(wrapper.get('h3').text()).toBe('关联文献（2）')
 expect(wrapper.findAll('li')).toHaveLength(2)
 expect(wrapper.get('li[data-document-id="doc-a"]').attributes('data-current')).toBe('true')
 expect(wrapper.get('li[data-document-id="doc-a"]').text()).toContain('Document A')
 expect(wrapper.get('li[data-document-id="doc-a"]').text()).toContain('当前文献')
 expect(wrapper.get('li[data-document-id="doc-b"]').attributes('data-current')).toBe('false')
 expect(wrapper.findAll('.note-document-current')).toHaveLength(1)
})

it('changes only the current marker on prop updates without mutating or filtering the input collection',async()=>{
 const source=documents(),before=JSON.stringify(source)
 for(const document of source)Object.freeze(document)
 Object.freeze(source)
 wrapper=mount(NoteDocuments,{props:{documents:source,currentDocumentId:'doc-a'}})
 await wrapper.setProps({currentDocumentId:'doc-b'})
 expect(wrapper.get('h3').text()).toBe('关联文献（2）')
 expect(wrapper.findAll('li').map(row=>row.attributes('data-document-id'))).toEqual(['doc-a','doc-b'])
 expect(wrapper.get('li[data-document-id="doc-a"]').attributes('data-current')).toBe('false')
 expect(wrapper.get('li[data-document-id="doc-b"]').attributes('data-current')).toBe('true')
 expect(JSON.stringify(source)).toBe(before)
})

it('emits another document ID but never navigates from the current document title',async()=>{
 wrapper=mount(NoteDocuments,{props:{documents:documents(),currentDocumentId:'doc-a'}})
 await wrapper.get('li[data-document-id="doc-a"] .note-document-title').trigger('click')
 expect(wrapper.emitted('open-document')).toBeUndefined()
 await wrapper.get('button[aria-label="打开关联文献：Document B"]').trigger('click')
 expect(wrapper.emitted('open-document')).toEqual([['doc-b']])
})

it('retains full long titles for display and hover and renders markup only as text',()=>{
 const longTitle='A complete research title '.repeat(15)+'<img src=x onerror=alert(1)>'
 wrapper=mount(NoteDocuments,{props:{documents:[{id:'doc-b',title:longTitle}],currentDocumentId:'doc-a'}})
 const link=wrapper.get('button')
 expect(link.text()).toBe(longTitle)
 expect(link.attributes('title')).toBe(longTitle)
 expect(wrapper.find('img').exists()).toBe(false)
})

it('provides an empty-title fallback and an explicit empty association state',async()=>{
 wrapper=mount(NoteDocuments,{props:{documents:[{id:'doc-b',title:'   '}],currentDocumentId:'doc-a',label:'个人笔记N的关联文献'}})
 expect(wrapper.get('section').attributes('aria-label')).toBe('个人笔记N的关联文献')
 expect(wrapper.get('button').text()).toBe('未命名文献')
 expect(wrapper.get('button').attributes('title')).toBe('未命名文献')
 await wrapper.setProps({documents:[]})
 expect(wrapper.get('h3').text()).toBe('关联文献（0）')
 expect(wrapper.text()).toContain('尚未关联文献')
 expect(wrapper.findAll('li')).toHaveLength(0)
})

it('prevents navigation while disabled and keeps all rows visible',async()=>{
 wrapper=mount(NoteDocuments,{props:{documents:documents(),currentDocumentId:'doc-a',disabled:true}})
 const button=wrapper.get('button')
 expect((button.element as HTMLButtonElement).disabled).toBe(true)
 await button.trigger('click')
 expect(wrapper.emitted('open-document')).toBeUndefined()
 expect(wrapper.findAll('li')).toHaveLength(2)
})
