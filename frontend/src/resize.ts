// Shared by the library sidebar and reader panel. Pointer capture keeps drags local.
export function startPointerResize(event: PointerEvent, startWidth: number, update: (width: number) => void, direction = 1) {
  const target = event.currentTarget as HTMLElement
  target.setPointerCapture(event.pointerId)
  const start = event.clientX
  const move = (e: PointerEvent) => update(startWidth + direction * (e.clientX - start))
  const stop = () => {
    target.removeEventListener('pointermove', move); target.removeEventListener('pointerup', stop)
    target.removeEventListener('pointercancel', stop); target.removeEventListener('lostpointercapture', stop)
  }
  target.addEventListener('pointermove', move); target.addEventListener('pointerup', stop)
  target.addEventListener('pointercancel', stop); target.addEventListener('lostpointercapture', stop)
  return stop
}
