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

## Open Questions

UI 初始宽度、图标素材和性能样本文献见公共 Q2/Q7。改变数值不改变面板事件或权限契约。
