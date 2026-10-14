# Proposal

## Why

科研阅读需要在不离开当前 PDF 的情况下理解中英文词句和段落。明确翻译和阅读器/笔记的边界可以让成员独立接入真实服务。

## What Changes

- 规划词语、句子、段落及选区的中英双向翻译。
- 规划侧栏原文/译文、复制和通过 04 保存笔记。
- 定义请求、结果、上下文一致性、失败与权限场景；供应商与额度见待确认项。
- 不包含全文 PDF 翻译、CAJ 或商业学科工作台。本次不实现翻译服务或页面。

## Capabilities

### New Capabilities

- `literature-translation`: 当前私有文献文本翻译、结果呈现与输出。

### Modified Capabilities

无。

## Impact

负责人Siguo Liu；状态待实现。未来涉及 translation 前端/API、供应商适配器和来源结果存储；依赖 01 权限、02 文本选择、04 笔记保存契约。全部实现任务未勾选。契约见 `docs/design/api-contracts.md`。
