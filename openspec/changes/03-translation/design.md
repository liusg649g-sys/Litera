> 当前状态（2026-10-26）：文献翻译及与笔记联动已实现并通过用户统一验收；本文后续包含上游历史设计。实际扁平API、签名回执、个人模型与测试边界见tasks.md、docs/design/api-contracts.md和docs/delivery/github-delivery.md；不把旧NoteDraft/translationId规划当当前已实现接口。

# Design

## Context

动机见 proposal.md。Siguo Liu负责，待实现。当前没有翻译 API/供应商配置或 UI；依赖 01 权限、02 ReaderContext，通过 04 NoteDraft 保存。公共 [API](../../../docs/design/api-contracts.md) 为预期契约。

## Goals / Non-Goals

**Goals:** 接入供应商可替换，结果关联阅读上下文，复制/保存失败可观察。

**Non-Goals:** 不包含整篇 PDF 翻译或学科收费产品，不直接写 notes 表、不创建供应商代码。

## Decisions

1. 后端翻译适配器处理密钥、长度/语言校验、超时与标准错误；前端只提交已选文本。相比浏览器直连供应商，可统一权限且不泄漏 key；仅送所需选段。
2. 请求含 ReaderContext，结果含 documentId/contextRevision，旧结果不进入新选区。UI 复用右面板，状态为 idle/loading/success/error，不复制阅读器布局逻辑。
3. 真实翻译结果存本人来源记录以提供 translationId；保存笔记走 04 公共接口。相比直接写笔记表，来源验证和未来接口演进可统一管理。
4. 源/目标只支持 zh/en，复制操作处理剪贴板失败。04 未接入时禁用保存，避免假成功。

## Risks / Trade-offs

- [外部调用延迟/额度] → 配置限制、取消、超时反馈和重试；不覆盖先前结果。
- [选区变化串结果] → documentId/contextRevision 检查。
- [发送不必要文献内容] → 仅选段和最小上下文，服务端密钥配置，日志避免正文。

## Migration Plan

后续明确启动本模块后增加来源结果迁移/适配器 → API 及测试 → 侧栏复制 → 04 接入后保存联调。供应商不可用回退为禁用入口，保留来源数据；不影响 01/02 阅读。

## Open Questions

Q3 的供应商、额度、长度上限、超时/缓存配置待实现前确认；通过适配器和配置解决，不改变中英选区契约。
