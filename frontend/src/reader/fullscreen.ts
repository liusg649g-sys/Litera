import { nextTick, onBeforeUnmount, onMounted, ref, type InjectionKey, type Ref } from 'vue'

export const readerPopupRoot:InjectionKey<Ref<HTMLElement|undefined>>=Symbol('reader-popup-root')
let exitedAt=-Infinity
// Ignore reader-specific Escape actions during native fullscreen and its exit.
// Never preventDefault/stopPropagation here; the browser owns fullscreen Escape.
export function nativeFullscreenEscape(){return !!document.fullscreenElement || performance.now()-exitedAt<500}

export function useReaderFullscreen(root:Ref<HTMLElement|undefined>,message:(text:string)=>void,position:()=>()=>void,settled:()=>Promise<void>){
  const active=ref(false),pending=ref(false),transitioning=ref(false)
  let restore:(()=>void)|undefined,disposed=false,revision=0
  async function changed(){
    const next=document.fullscreenElement===root.value
    if(next===active.value)return
    const keep=restore || position(),token=++revision;restore=undefined
    if(!next)exitedAt=performance.now()
    transitioning.value=true;active.value=next
    await nextTick()
    // Flush the new height/transform styles, then wait for the real 200ms CSS
    // transitions. Reduced motion has no animations and settles immediately.
    const brand=root.value?.querySelector<HTMLElement>('.reader-brandbar-slot')
    brand?.getBoundingClientRect()
    const animations=[...(brand?.getAnimations() || []),...(brand?.firstElementChild?.getAnimations() || [])]
    await Promise.allSettled(animations.map(animation=>animation.finished))
    if(disposed || token!==revision)return
    await settled()
    if(disposed || token!==revision)return
    keep();transitioning.value=false
  }
  async function toggle(){
    if(pending.value || transitioning.value)return
    if(!root.value?.requestFullscreen || !document.fullscreenEnabled){message('当前浏览器不支持全屏阅读，请使用支持全屏的浏览器。');return}
    pending.value=true;restore=position()
    try{
      if(document.fullscreenElement===root.value)await document.exitFullscreen()
      else await root.value.requestFullscreen()
    }catch{restore=undefined;message('无法切换全屏，请检查浏览器的全屏权限后重试。')}
    finally{pending.value=false}
  }
  onMounted(()=>document.addEventListener('fullscreenchange',changed))
  onBeforeUnmount(()=>{
    disposed=true;revision++
    document.removeEventListener('fullscreenchange',changed)
    if(document.fullscreenElement===root.value)void document.exitFullscreen().catch(()=>{})
  })
  return {active,pending,transitioning,toggle}
}
