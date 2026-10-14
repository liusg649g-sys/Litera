# 六模块总览

Litera 的功能分为以下六个独立 OpenSpec change：

| 模块 | 主要用途 | 负责人 |
| --- | --- | --- |
| [01 文献管理](01-literature-management/proposal.md) | 注册登录与个人资料；PDF 导入、查看下载、分类检索、手工题录编辑、最近阅读及回收站。 | Jensen Zhang |
| [02 PDF 阅读与文献编辑](02-pdf-reader/proposal.md) | 在线阅读 PDF，支持搜索、选区、标注、书签、阅读进度、多标签和可伸缩面板；不改写 PDF 正文。 | Jensen Zhang |
| [03 文献翻译](03-translation/proposal.md) | 翻译中英文词句、段落与选区，在侧栏展示原文和译文，支持复制及保存笔记。 | Siguo Liu |
| [04 文献笔记](04-literature-notes/proposal.md) | 管理和搜索个人笔记，保存原文摘录、翻译及 AI 回答，并关联文献与页码。 | Siguo Liu |
| [05 文献信息自动提取](05-metadata-extraction/proposal.md) | 从 PDF 提取题录候选和带页码正文，支持人工校正，为 RAG 提供原文数据。 | Jialu Ma |
| [06 AI 文献智能问答](06-ai-qa/proposal.md) | 基于当前文献提供摘要、研究结构解析和问答，返回原文引用及页码，证据不足时明确提示。 | Jialu Ma |

六个 change 均已完成规划；01 的P1用户认证已实现，P2文献库业务、02及03–06仍待开发。每个目录内的 `proposal.md` 说明范围，`design.md` 说明方案，`specs/` 定义需求场景，`tasks.md` 列出后续实现任务。

文献管理提供基础数据，阅读器提供选区与上下文；信息提取向 AI 问答提供正文，翻译和 AI 结果可保存为笔记。开发先按注册登录 → 文献库 → PDF 阅读器推进。

[返回项目 README](../../README.md) · [设计文档索引](../../docs/design/README.md)
