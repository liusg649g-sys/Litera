# Reader 公共接入契约

2026-10-17，P3-C2。源码真源为 `frontend/src/reader/context.ts` 与 `navigation.ts`。
只提供跨模块契约，不实现 Change 03–06 的界面、数据库或供应商调用。

## 快照与事件

02 ReaderPage 是唯一阅读快照生产者；03/04/06 订阅，05 仅复用文献ID及物理页码。
`readerContext.value` 为不可变快照或 null。字段为 documentId、pageNumber、selectedText、
selectionPosition、annotationId、contextRevision。pageNumber 为当前阅读的物理1-based页码；
选区的起始页及跨页范围始终从 selectionPosition 各项 pageNumber 取得，不使用印刷页码。
选区坐标相对未旋转 CropBox 左上角归一化；textRanges 是 PDF.js item 内 UTF-16 半开区间，
与未来05的 Unicode code point chunk offset 不可混用。DPR/屏幕坐标不进入公共持久坐标。

事件包括 document-change（真实PDF已就绪）、page-change（物理当前页变化）、selection-change、
context-change（模式/所选批注变化）和 context-cleared（切换开始、失败、退出/销毁）。
DOM 事件为 `litera:reader:<事件名>`，detail 为同一个快照或 null。
revision 在本SPA工作区全局单调递增，A→B→A不复用旧值，刷新后重新开始。
空选区为 `selectedText=''`、`selectionPosition=null`；annotationId 为当前选中的本篇Litera对象或 null。
消费者不得修改快照、将上下文当权限凭据，或把订阅者异常传播到阅读器。

```ts
import { subscribeReaderContext, isReaderContextCurrent } from './reader/context'
const lifecycle = new AbortController()
const stop = subscribeReaderContext(async (_event, snapshot) => {
  if (!snapshot?.selectedText) return
  // consumeSelection由消费者模块实现；此处不产生假业务结果。
  const result = await consumeSelection(snapshot, lifecycle.signal)
  if (!lifecycle.signal.aborted && isReaderContextCurrent(snapshot)) applyResult(result)
}, lifecycle.signal)
// 组件卸载/权限失效时停止消费者自己的请求与订阅。
lifecycle.abort()
stop() // 幂等，也支持不提供signal时手工取消订阅。
```

## 导航适配器

`navigateReader(location, {signal?, context?})` 返回可判别结果：
`{status:'ok'}`、`{status:'unavailable',code,message}` 或 `{status:'error',code,message}`。
location 为 `{documentId,pageNumber,position?:SelectionPosition,annotationId?:string}`。
每次先调用现有受保护 GET document API 检查本人有效文献，再交给活动 ReaderPage。
跨文献复用正常路由/草稿守卫、真实PDF加载和页数验证，不绕开保存队列。
position 导航使用第一个归一化矩形定位；annotationId 必须属于本篇目标页。
ok 表示定位已接受；尚未渲染页的精确滚动会在真实页面ready后完成。

```ts
const result = await navigateReader({documentId, pageNumber: 12}, {signal})
if (result.status !== 'ok') showMessage(result.message)
// 若由某次选区异步结果发起，传 context:snapshot，拒绝过期响应。
await navigateReader({documentId, pageNumber: 12, position}, {context:snapshot, signal})
```

普通导航不依赖05。引用导航接受现有 Citation：documentId/extractionVersion/chunkId/pageNumber/quote。
05未来通过 `registerCitationResolver` 提供真实版本/分块/quote核验和可信位置，返回 null 表示失效；
注销函数由该模块生命周期调用。未注册时返回 SOURCE_UNAVAILABLE，不用页码伪装引用有效。
ReaderPage 自己注册/卸载 `registerReaderNavigation`，其他业务模块只调用 navigateReader。
文献库中没有活动阅读器时返回 READER_UNAVAILABLE；消费者可先由既有文献入口打开阅读器再请求定位。
无权限/不存在保留真实401/404错误，非法页码/越界坐标/错页批注明确失败；取消/旧revision为 STALE_CONTEXT。

contextRevision、progress.version、annotationRevision/对象version、extractionVersion 分属不同域，不能互相代替。
02不拥有03–06异步请求；消费者必须在context-cleared或自身卸载时取消自己的请求并校验结果，
ReaderPage负责清空选区、自己的监听器、PDF/Worker/Canvas及导航宿主。
