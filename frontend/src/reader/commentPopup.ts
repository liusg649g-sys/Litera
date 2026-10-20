import { shallowReactive } from 'vue'

// A single popup belongs to the active reader; no annotation data is mutated.
export const commentPopup=shallowReactive({open:false,pinned:false,key:'',content:'',anchor:undefined as Element|undefined})
let cleanupTimer:ReturnType<typeof setTimeout>|undefined
export function showComment(key:string,content:string|null,anchor:Element,pinned=false){
  if(!pinned && commentPopup.open && commentPopup.pinned)return
  clearTimeout(cleanupTimer)
  Object.assign(commentPopup,{open:true,pinned,key,content:content || '',anchor})
}
export function leaveComment(key:string){if(commentPopup.key===key && !commentPopup.pinned)dismissComment()}
export function dismissComment(){
  clearTimeout(cleanupTimer);commentPopup.open=false;commentPopup.pinned=false
  cleanupTimer=setTimeout(()=>{if(!commentPopup.open){commentPopup.anchor=undefined;commentPopup.content='';commentPopup.key=''}},100)
}
export function clearComment(){clearTimeout(cleanupTimer);Object.assign(commentPopup,{open:false,pinned:false,key:'',content:'',anchor:undefined})}
