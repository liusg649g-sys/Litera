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


## 2026-10-22 文字映射可靠性元数据

ReaderContext可选textExtractionIssue（string/null）用于提示选区或字体无法可靠映射Unicode。原selectedText、selectionPosition、textRanges/坐标和revision语义不变；没有异常的快照可以不带此字段。翻译消费者必须在提示存在时拒绝模型调用，不能自行删字符。此字段是客户端提示而非权限或服务器可信证明；服务端还需独立检查。说明见pdf-text-reliability.md。本轮不接笔记业务或更改批注API。

## P3-A 笔记接入（2026-10-23）

ReaderContext 的生产者/消费者字段均不改变。NotesPanel 用 ReaderPage 的 route.params.documentId 作为当前文献，只订阅认证账号，不把搜索框/笔记选区当成 PDF 选区。持久化走独立 notes API，不写原 PDF、批注和翻译结果。未来来源插入使用 sourceSchemaVersion/sources 扩展，与 note_documents 多对多复用分离。

ReaderPage 将翻译与笔记放入共享扩展布局容器，但两个开关和组件状态独立保留。离开阅读器或切换文献先等待 notesPanel.beforeLeave()；保存失败/冲突阻止导航，保留按用户/笔记隔离的会话草稿。关闭侧栏只隐藏，不销毁编辑器。1700px及以上并排、1100–1699px右侧上下排列，较窄窗口为底部上下抽屉。旧 ReaderPanel 非扩展消费者不受新样式作用域影响。


## P3-A 关联文献标题导航（2026-10-23）

NoteDocuments是纯展示消费者，完整展示DTO.documents，不对当前阅读ID过滤；props.currentDocumentId仅派生标识。NotesPanel.openDocument调用现有navigateReader，复用保护性文献GET、ReaderPage路由草稿守卫和真实PDF加载。ReaderLocation/NavigationResult/ReaderContext均无字段变更，生产者保持兼容。

切换到另一篇已关联文献时，notes.setDocument携带同一条已保存笔记而非只恢复目标文献以前的选择；集合仍取完整服务端DTO。导航只发送读取笔记/文献请求，正常阅读进度沿用原行为，不创建/解除笔记关系。未保存/权限失败/用户改变路由/账号变化均有保护，不绕过现有批注与进度守卫。该接入仅关联文献标题打开PDF，不是P3-B来源摘录或页码引用插入。
## P3-B ReaderContext 消费约定（2026-10-23）

复用既有只读 `ReaderContext` 和 `SelectionPosition`，不修改事件或旧 `NoteDraft` 公共接口。`reader/noteCapture.ts` 只把当前 PDF 文字层的可靠选区转换为 `NoteCaptureDraft`；普通输入框选择没有 PDF 位置，不会成为摘录。原始文字、物理页码和位置元数据使用独立副本，批注坐标不变。

ReaderPage 的“添加到笔记”和 TranslationPanel 的“保存到笔记”共用目标选择对话框。打开前先刷新当前笔记的自动保存；失败则阻止插入。保存意图在焦点变化前冻结，文献或账号真实切换会关闭对话框，迟到响应不能写入新目标。

“当前译文”必须同时匹配实际 ReaderContext 的文献、选区、物理页码、位置和方向。选区已经变化时，只能作为明确标识的历史结果保存，并使用结果自己的来源。来源卡使用服务器快照显示，当前标签不会替换文献标题或页码；精确跳转留给 P3-C。

## P3-C2-A 可靠来源页导航（2026-10-25）

`ReaderLocation` 新增可选 `fileSha256`。存在该字段即表示结构化笔记来源导航：公共 `navigateReader` 必须先通过受保护的 `GET /documents/{id}` 核对当前用户权限、当前附件 SHA256 和已知 `pageCount`，再把请求交给 ReaderPage。哈希缺失/变化、页码非法、404/权限错误或宿主加载失败统一显示“无法可靠定位来源”，不得用当前标签、标题或正文相似度猜测来源。普通关联文献导航不带该字段，原行为保持兼容。

ReaderPage 仍是唯一导航宿主，复用已有标签、路由守卫、PDF 加载和 `pdf.numPages` 页数复核；来源 PDF 已打开时切到原标签，未打开时走正常阅读路由。`NotesPanel.openSource` 先等待既有 800ms 自动保存队列 `flush()`，保存失败或修订冲突时阻止跳转；成功后保持同一笔记编辑状态，不创建或解除关联。快速连续来源点击通过 AbortController 和尝试序号使旧请求失效。本阶段只到物理页，不消费保存的选区坐标、不做文字重匹配或高亮。

## P3-C2-B1 可复核选区临时高亮（2026-10-26）

结构化来源导航的成功结果增量扩展为 `{status:'ok', precision?:'page'|'exact', message?:string}`；既有只判断 `status` 的消费者保持兼容。`NotesPanel` 只把来源首个物理页中同时具有合法归一化矩形、非空 `textQuote` 和有序 `textRanges` 的位置交给阅读器。C2-A 的文献权限、SHA256、页码、标签与草稿保护仍先执行。

`PdfPage` 等待当前 PDF.js TextLayer 完成后，按保存的文字项索引与 UTF-16 半开范围逐段重建 `textQuote`。只允许 CRLF 统一及首尾空白处理；逐字不一致、范围越界、缺少范围、无可见 DOM Range 或超时都返回 `precision:'page'`，不做相似文本或首次出现匹配。验证成功的矩形来自当前 DOM Range，因此适配当前缩放和 PDF 内置旋转；高亮是 `pointer-events:none` 的临时显示层，不写入 PDF、批注或数据库。

`registerReaderSourceReset` 让每次新来源请求在权限检查前清理旧高亮。ReaderPage 使用独立 token、AbortSignal 和文献 generation 过滤迟到结果，只在第一次精确成功时将多个矩形的并集滚动到阅读区域中央；同一来源因缩放或虚拟化重绘可重建高亮，但不再次抢夺滚动。文献切换、标签关闭/阅读器销毁及账号变化会清理。跨物理页连续选区、用户主动旋转后的适配、模糊重匹配和 OCR 不属于 B1。
