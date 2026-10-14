# Litera 设计与规约索引

日期：2026-10-14。项目：科研文献智能管理与协作平台，《互联网软件开发技术与实践》课程小组项目。

[项目 README](../../README.md) · [六模块总览](../../openspec/changes/README.md)

本批交付仅为需求、架构和 OpenSpec 规划。不存在已完成的业务页面、API、数据表或 AI 服务。所有 change 的实现任务保持未勾选；OpenSpec artifact 的 done 仅代表文档存在。

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
| [01-literature-management](../../openspec/changes/01-literature-management/proposal.md) | Jensen Zhang | user-auth、literature-library | 待开发；第一阶段 |
| [02-pdf-reader](../../openspec/changes/02-pdf-reader/proposal.md) | Jensen Zhang | pdf-reading、reader-workspace | 待开发；第二阶段 |
| [03-translation](../../openspec/changes/03-translation/proposal.md) | Siguo Liu | literature-translation | 待实现 |
| [04-literature-notes](../../openspec/changes/04-literature-notes/proposal.md) | Siguo Liu | literature-notes | 待实现 |
| [05-metadata-extraction](../../openspec/changes/05-metadata-extraction/proposal.md) | Jialu Ma | metadata-extraction | 待实现 |
| [06-ai-qa](../../openspec/changes/06-ai-qa/proposal.md) | Jialu Ma | document-qa | 待实现 |

每个 change 均有 proposal、design、delta specs 和 tasks。主规格 `openspec/specs/` 仍为空；实现并验收后再同步或归档，避免把目标行为标为现有能力。

## 已检查的输入

已读取用户粘贴的项目总体规约与六模块设计需求全文，以及 `docs/references/xiaolvjing/1.png` 至 `5.png` 全部截图。仓库没有另附选题文档；当前以该需求全文作为选题与范围依据。如另有课程原始选题书，需后续比对，不声称已读取不存在的文件。

初始 Git 状态：master 分支无提交，`.agents/`、`.claude/`、`docs/`、`openspec/` 未跟踪。frontend、backend、scripts、storage 为空。OpenSpec 1.14.1，repo-local root，schema 为 spec-driven，无既有 change、主规格或业务配置。
