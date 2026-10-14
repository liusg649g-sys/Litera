# Proposal

## Why

用户需把阅读摘录、翻译和 AI 回答整理为可检索的个人笔记，并保留文献与页码来源。统一保存接口可以避免各模块分别存储不兼容的笔记。

## What Changes

- 规划个人文献笔记 CRUD、搜索、页码/批注关联和来源快照。
- 规划统一 NoteDraft 接收手动笔记、PDF 原文、译文及 AI 回答/引用。
- 明确版本冲突、用户隔离和文献删除/恢复关联。
- 不规划多人共编、知识图谱或公开分享；本次不实现笔记系统。

## Capabilities

### New Capabilities

- `literature-notes`: 私有文献笔记生命周期、来源追溯与个人搜索。

### Modified Capabilities

无。

## Impact

负责人Siguo Liu；状态待实现。未来涉及 notes 前端/API、notes 实体，依赖 01 文献/身份，接收 02/03/06 NoteDraft；不依赖其他成员完成服务才定义公共格式。全部实现任务未勾选，见 `docs/design/data-model.md` 与 API 契约。
