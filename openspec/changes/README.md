# 六模块总览

Litera 的功能分为以下六个独立 OpenSpec change：

| 模块 | 主要用途 | 负责人 |
| --- | --- | --- |
| [01 文献管理](01-literature-management/proposal.md) | 注册登录与个人资料；PDF 导入、查看下载、分类检索、手工题录编辑、最近阅读及回收站。 | Jensen Zhang |
| [02 PDF 阅读与文献编辑](02-pdf-reader/proposal.md) | 在线阅读 PDF，支持三种视图、搜索/选区、14类标注/插入、阅读进度、批注导出、多标签和可伸缩面板；不改写 PDF 正文。 | Jensen Zhang |
| [03 文献翻译](03-translation/proposal.md) | 翻译中英文词句、段落与选区，在侧栏展示原文和译文，支持复制及保存笔记。 | Siguo Liu |
| [04 文献笔记](04-literature-notes/proposal.md) | 管理和搜索个人笔记，保存原文摘录、翻译及 AI 回答，并关联文献与页码。 | Siguo Liu |
| [05 文献信息自动提取](05-metadata-extraction/proposal.md) | 从 PDF 提取题录候选和带页码正文，支持人工校正，为 RAG 提供原文数据。 | Jialu Ma |
| [06 AI 文献智能问答](06-ai-qa/proposal.md) | 基于当前文献提供摘要、研究结构解析和问答，返回原文引用及页码，证据不足时明确提示。 | Jialu Ma |

六个change均已完成规划；01的P1/P2-A/P2-B及UI优化已通过用户实际功能/UI验收（任务33/34，5.A1仅剩专项MySQL测试补证），尚未归档。02的P3-A1/A2/B1均已通过实际功能/UI验收，P3-B1于2026-10-16正式交付，当前18/36；下一阶段P3-B2（4.1–4.6）尚未启动，B2/C1/C2仍须新会话授权，Change 02未归档。03–06分别0/6、0/6、0/7、0/8，均未开发，需单独启动。每个目录内proposal/design/specs/tasks分别记录范围、设计、场景和实际任务状态。

文献管理提供基础数据，阅读器提供选区与上下文；信息提取向 AI 问答提供正文，翻译和 AI 结果可保存为笔记。开发先按注册登录 → 文献库 → PDF 阅读器推进。

[返回项目 README](../../README.md) · [设计文档索引](../../docs/design/README.md)
