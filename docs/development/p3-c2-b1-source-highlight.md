# P3-C2-B1：PDF 原文精确定位与临时高亮

日期：2026-10-26。范围只包括来源身份、PDF SHA256 和物理页码均已通过 P3-C2-A 校验后，对可由当前 PDF.js 文字层严格复核的保存选区做一次性滚动与临时高亮。没有数据库迁移，不修改来源、PDF 或批注；5180 继续使用隔离 SQLite 与 Mock 翻译。

## 现有元数据与可靠性边界

P3-B 的 `SelectionPosition` 已保存物理页码、未旋转 CropBox 归一化矩形、页内 `textQuote`，以及 PDF.js 文字项索引和 UTF-16 半开范围 `textRanges`。跨行选区会保存多个范围和多个矩形。服务端只验证原文属于真实 PDF 页面并将精度标为 `page`，没有把客户端坐标升级为服务端精确证明。

B1 不直接绘制旧坐标，也不按相似文本搜索。`frontend/src/reader/sourceHighlight.ts` 先验证保存结构；`PdfPage.updateSourceHighlight` 再从当前 TextLayer 的相同 item/range 重建文字，只有逐字等于保存 `textQuote` 且 DOM Range 产生可见矩形时才返回 `exact`。旧来源缺少 `textRanges`、文字层变化、范围越界或渲染超时只保留可靠页跳转。

## 实现

- `NotesPanel.openSource` 继续先刷新笔记草稿，再把可靠位置连同不可变文献 ID、SHA256 和页码传给公共导航；界面区分“精确定位”与“只能定位到页面”。
- `navigation.navigateReader` 保留 C2-A 全部校验，成功结果增加可选 `precision/message`，并通过 `registerReaderSourceReset` 在新来源请求开始时清理旧高亮。
- `PdfPage` 在 TextLayer 渲染后用 DOM Range 生成单行或多行矩形，显示独立、不可交互的橙色临时层；缩放或虚拟化重绘时按同一范围重建，不创建永久批注。
- `ReaderPage` 使用递增 token、取消信号和文献生命周期过滤旧结果；精确结果只滚动一次到全部高亮矩形并集附近中央。切换文献、关闭阅读器或账号变化会清理。

高亮仅处理来源记录的首个物理页。用户主动页面旋转、跨物理页连续高亮、没有 `textRanges` 的旧来源重建、OCR 和模糊匹配留待后续单独授权。

## 本轮验证

- 前端 Vitest：26 个文件、190 项通过。
- 前端类型检查及生产构建：通过；保留现有大 chunk 提示。
- 后端笔记/来源回归：73 项通过；只有既有 Starlette/httpx 弃用警告。
- 隔离 Playwright 摘录套件：13 项通过、1 项本机私人 PDF opt-in 跳过。真实 PDF.js 覆盖单行跨文献、同文献重用、多行多个矩形、搜索结果跳转、旧来源页级降级和哈希不一致拒绝。
- 隔离 Reader Playwright：公共导航和文字批注 2 项通过。
- OpenSpec strict：通过。

自动化结果不替代用户在 5180 的视觉验收。缩放、用户旋转及更复杂历史来源属于后续 B2，B1 不宣称已支持。
