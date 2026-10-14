# Design

## Context

动机见 proposal.md。Siguo Liu负责，待实现。当前 notes 代码/数据表为空；来源可能来自 02 选区、03 翻译或 06 回答，统一 [NoteDraft](../../../docs/design/api-contracts.md) 已规划。

## Goals / Non-Goals

**Goals:** 私有笔记拥有明确文献、物理页码和来源，模块无需相互写表。

**Non-Goals:** 不提供共编、分享或富 HTML 执行，不依赖未完成的 AI 才能使用手工笔记。

## Decisions

1. 独立 notes API 校验 owner 与文献有效性，并验证 sourceType/sourceId、annotationId、引用关联。多态来源使用服务层验证，不能用伪外键代替。
2. 保存内容与来源快照；批注删除清空 annotationId 但保留笔记文本。相比只存来源链接，不会因批注删除丢失已整理内容；文献永久删除仍清理笔记。
3. content 为安全 string，首版无危险 HTML；支持手工/选区/翻译/AI 草稿。UI 控件可后选，渲染净化在确定控件后测试。
4. 使用 version 乐观并发；个人搜索分页且遵守父文献 deletedAt 过滤。共享错误/分页见公共 API，实体关系见 [数据模型](../../../docs/design/data-model.md)。

## Risks / Trade-offs

- [来源伪造或越权] → 校验每个来源及其所属文献/用户。
- [并发笔记覆盖] → CAS 与冲突提示，保留输入。
- [原文含脚本] → 安全文本渲染与 XSS 测试。

## Migration Plan

后续创建 notes 表 → CRUD/搜索与权限测试 → 文献侧栏接入 → 02/03/06 来源联调，未接入来源先保持禁用。回退禁用 UI/API，保留笔记数据，禁止以回退为由清空个人笔记。

## Open Questions

Q4 的编辑控件、受限 Markdown 展示及内容长度配置可在前端实现前选择；不改变正文 string 和安全要求。
