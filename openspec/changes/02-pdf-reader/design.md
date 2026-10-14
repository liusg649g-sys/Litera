# Design

## Context

动机见 proposal.md；当前无阅读器实现。依赖 01 的已验收认证、PDF 内容、元数据和阅读记录。截图 3–5 已逐张分析，见 [UI 规范](../../../docs/design/ui-guidelines.md)。Jensen Zhang负责 P3，本批仅规划。

## Goals / Non-Goals

**Goals:** 标注位置跨缩放/旋转稳定，标签状态隔离，提供可独立接入的阅读上下文与面板事件。

**Non-Goals:** 不编辑 PDF 文件正文，不实现翻译、笔记和问答；不把占位面板当作业务已完成。

## Decisions

1. PDF.js 文本层与自有标注覆盖层分离，通过 01 Cookie/Range 内容接口加载；相比改写 PDF 字节，覆盖层便于 CRUD、权限和原文件保真。
2. 标注坐标持久化为未旋转页面的归一化矩形，多页选区按页数组；视图转换处理缩放/旋转/DPR。相对 CSS 像素更稳定；结构见 [API 契约](../../../docs/design/api-contracts.md)。书签为页级，批注支持页级/选区级。
3. 阅读进度沿用 01 reading_progress 并 CAS 更新；总页数由轻量 PDF 结构读取校验，不依赖 05 自动正文解析。页码统一物理 1-based，避免 PDF 印刷页标签歧义。
4. 工作区以 documentId 管理标签，contextRevision 标记快照；切换取消/丢弃旧请求。组件树、props/events、功能状态注册与布局状态见 UI 文档；使用公共 contracts 而非模块互相直接依赖业务实现。
5. 右侧一次展开一个面板，AI 收起显示悬浮按钮；布局层不执行智能请求。狭窄视口切为抽屉，相比同时铺开三栏可保留 PDF 可读宽度。
6. 题录修改复用 01 PATCH，所有 annotations/progress 访问复用 owner 过滤并验证嵌套文献关系。

## Risks / Trade-offs

- [不同页面尺寸/旋转导致标注错位] → 归一化转换与多尺寸/旋转样例验证。
- [离开页面保存失败] → 未保存状态、关闭确认与显式重试，不只依赖 unload。
- [多标签异步结果串文献] → 文献+contextRevision 校验，取消请求测试。
- [扫描 PDF 无文本] → 明确搜索/选区不可用；OCR 不在本 change。

## Migration Plan

01 P2 验收后增加 annotations 和必要的进度字段/页数校验；接入真实 PDF.js → 标注/进度 → 工作区/公共事件，按 tasks 分组验证。回退禁用 reader 入口，保留新标注表和原 PDF；不为回退删除用户标注。

## 2026-10-15 接入核对（仅交接，未开发）

01已通过用户功能/UI验收；02仍为0/12，下一会话须获明确实施指令。下列为关键代码核对结果，详细契约见[API](../../../docs/design/api-contracts.md)、[模型](../../../docs/design/data-model.md)和[UI组件事件](../../../docs/design/ui-guidelines.md)。

| 接入点 | 当前实际实现 | 02需要补齐 |
| --- | --- | --- |
| 文献入口 | frontend/src/router.ts的/reader/:documentId跳/library?documentId=…&readerPending=1；LibraryPage阅读按钮直接浏览器预览 | 创建受保护reader路由并对接阅读按钮，稳定复用documentId；保留独立下载 |
| 身份与元数据 | auth.ts恢复会话；api.ts同源Cookie、CSRF、401事件；GET/PATCH documents沿用DocumentDTO/version | 复用会话与题录组件，阅读资源逐次owner/active校验；退出取消任务并清阅读状态 |
| PDF内容 | GET /api/v1/documents/{id}/content，200完整或206单Range；Accept-Ranges、Content-Length、Content-Range、application/pdf；非法/多Range416 | 锁定pdfjs-dist及匹配worker，使用同源URL；验证真实Range加载，不能把JSON api<T>直接用作二进制读取 |
| 内容边界 | 无HEAD、ETag/If-Range专用实现；API响应no-store；Nginx不静态暴露PDF | 不依赖尚未提供的HEAD/缓存协商；PDF.js错误适配401/404/416，401接现有会话失效机制；切换销毁旧loadingTask/worker |
| 阅读记录 | library.py GET/PUT progress，PUT {}更新lastReadAt及独立version；pageNumber/zoom非null503 | 扩展原接口，服务端验证总页数；CAS保存/恢复页码和缩放，0为未读版本；不重复建表 |
| 页数及缩放 | documents.page_count尚为null；reading_progress.zoom为nullable字符串，DTO转float | 轻量结构读取物理总页数，独立于05；明确缩放合法范围/写入转换，必要迁移只作增量并保留旧记录 |
| 标注与生命周期 | 无annotations表/API；清理流程现只覆盖01关联 | 新增annotations与CRUD、嵌套权限/CAS；软删除保留、恢复原关联、永久清理覆盖标注，失败进入原清理状态/重试 |
| 跨模块接口 | ReaderContext/SelectionPosition/NoteDraft/Citation及组件事件只有文档契约 | 落地公共类型/事件；documentId+contextRevision拒绝旧响应，禁止提前调用未实现03/04/06 |

高亮/下划线存type、物理起始pageNumber、多页SelectionPosition[]及selectedText；矩形以未旋转页面左上角为原点归一化。书签可仅页码，批注可页级或选区级并有content；统一owner/document/version，原PDF字节不改。contextRevision、题录version、progress.version与annotation.version各自独立。

扩展边界：context-change/selection-change输出真实选区文本、页码、位置及文献快照；panel-toggle/panel-resize仅布局；save-note输出NoteDraft，04未接入时禁用保存并说明；citation-navigate校验文献/物理页/提取版本，05/06未就绪时不制造chunk或引用。阅读选区不依赖自动提取，AI证据依赖05已发布页文本。

实施顺序：P3-A锁定PDF.js/worker、真实内容与失败状态、导航/文本层/基础上下文；P3-B增量标注模型/API、覆盖层及进度CAS；P3-C多文献标签、面板/扩展事件、端到端与成员接入。各阶段先测再交付，全部任务本次保持未勾选。

记录的待处理边界：当前浏览器预览先PUT打开记录再导航PDF，lastReadAt代表发起打开，不保证已渲染成功；02应明确成功加载与进度保存的记录时机。当前专项MySQL测试日志未提供，下一阶段记录真实MySQL迁移/约束证据，不以SQLite代替。

## Open Questions

01已采用Element Plus Icons及自有品牌；02面板初始宽度、缩放范围/保存节流、PDF.js版本与兼容样本文献在P3-A/B实施前确定，容量与性能样本见公共Q7。改变布局数值不改变面板事件或权限契约。
