# Litera 设计与规约索引

日期：2026-10-14。项目：科研文献智能管理与协作平台，《互联网软件开发技术与实践》课程小组项目。

[项目 README](../../README.md) · [六模块总览](../../openspec/changes/README.md)

本目录为总体设计与规划索引。P1/P2-A/P2-B及UI优化已完成，用户已确认Change 01实际功能/UI验收通过，最新状态见[交接](../../HANDOFF.md)，历史证据见[P2-B记录](../development/p2-b.md)。专项MySQL自动化证据仍单独跟踪。PDF.js及其他成员模块待开发；artifact的done仅代表规划完成。

既有文献库布局优化历史见[P2-A UI记录](../development/p2-a-ui.md)。本轮P2-B在此布局上加入真实分类/筛选/历史/回收站，后端增量迁移与权限/清理状态同步实现；最新测试以P2-B记录为准。

## 公共文档

| 文档 | 内容 |
| --- | --- |
| [architecture.md](architecture.md) | B/S 技术链路、建议目录、部署、环境变量、Git 协作 |
| [ui-guidelines.md](ui-guidelines.md) | 五张截图分析、视觉、路由、布局、面板与悬浮助手 |
| [api-contracts.md](api-contracts.md) | REST API、DTO、错误和跨模块事件 |
| [data-model.md](data-model.md) | 实体、关联、隔离、删除和提取版本 |
| [module-dependencies.md](module-dependencies.md) | 六模块职责、依赖和接入边界 |
| [delivery-plan.md](delivery-plan.md) | 页面开发顺序、进度、测试与验收 |
| [decisions.md](decisions.md) | 重要设计建议与待确认项 |
| [validation.md](validation.md) | 本次 CLI 校验与覆盖核对结果 |

## 六个独立 change

| Change | 负责人 | 规格能力 | 实现状态 |
| --- | --- | --- | --- |
| [01-literature-management](../../openspec/changes/01-literature-management/proposal.md) | Jensen Zhang | user-auth、literature-library | P1/P2-A/P2-B与UI已通过用户验收；33/34，专项MySQL补证待完成；未归档 |
| [02-pdf-reader](../../openspec/changes/02-pdf-reader/proposal.md) | Jensen Zhang | pdf-reading、reader-workspace | 待开发；第二阶段 |
| [03-translation](../../openspec/changes/03-translation/proposal.md) | Siguo Liu | literature-translation | 待实现 |
| [04-literature-notes](../../openspec/changes/04-literature-notes/proposal.md) | Siguo Liu | literature-notes | 待实现 |
| [05-metadata-extraction](../../openspec/changes/05-metadata-extraction/proposal.md) | Jialu Ma | metadata-extraction | 待实现 |
| [06-ai-qa](../../openspec/changes/06-ai-qa/proposal.md) | Jialu Ma | document-qa | 待实现 |

每个 change 均有 proposal、design、delta specs 和 tasks。主规格 `openspec/specs/` 仍为空；实现并验收后再同步或归档，避免把目标行为标为现有能力。

## 已检查的输入

此前规划已读取总体规约、六模块需求及原1–5截图（现用户重命名为01–05）；本轮已读取06/07/08文献库参考图。仓库没有另附选题文档；如后续另有课程原始选题书再比对，不声称已读取不存在的文件。

初始 Git 状态：master 分支无提交，`.agents/`、`.claude/`、`docs/`、`openspec/` 未跟踪。frontend、backend、scripts、storage 为空。OpenSpec 1.14.1，repo-local root，schema 为 spec-driven，无既有 change、主规格或业务配置。


## P2-B当前落地（2026-10-14）

用户已明确启动并完成本轮01 P2-B代码：0003_library增量迁移、个人分类、组合检索、已打开进度子集/历史、软删除/恢复/清理状态与显式重试、原UI真实接入。新增兼容接口POST /cleanup-jobs/{jobId}/retry及nullable DocumentDTO.cleanupJob，仅影响01；具体行为、真实测试与手动MySQL验收见docs/development/p2-b.md、api-contracts.md和HANDOFF。保留P2-A段落为阶段历史，本轮不改变02–06的分工或启动边界。
