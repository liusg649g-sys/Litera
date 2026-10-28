# Litera 工程规范索引

适用：Litera与Litera-test的后续增量开发。2026-10-28依据第7课课件和当前源码审订；八份规范文本已齐，不表示八类要求全部实现或运行验收完成。原稿的草案状态/待团队确认保留，不代签组员批准。

## 八类文件与生效入口

| 顺序 | 规范 | 读取范围 |
| --- | --- | --- |
| 1 | [产品设计](1-product.md) | 页面/场景/四状态/术语/表单/视觉/可达性 |
| 2 | [后端开发](2-backend.md) | 分层/接口/错误/校验/事务/幂等/配置 |
| 3 | [安全开发](3-security.md) | 所有开发；授权/会话/机密/输入输出/依赖 |
| 4 | [测试](4-testing.md) | 用例来源、三类组织、隔离、命令与判定 |
| 5 | [部署运维](5-operations.md) | 构建/配置/启动/健康/日志/备份恢复/发布 |
| 6 | [AI应用](6-ai-application.md) | 模型调用/提示词/上下文/来源/评测/成本 |
| 7 | [数据](7-data-specification.md) | 模型/迁移/字典/分级/留存副本/一致性 |
| 8 | [评审与完成定义](8-review-specification.md) | 完成声明/规模/门禁/例外/证据/合并 |

长期入口：[AGENTS.md](../../AGENTS.md)。重复审查复用[litera-standards-review](../../.agents/skills/litera-standards-review/SKILL.md)，不另建Cursor规则或复制OpenSpec工作流。提案、实现、同步/归档仍使用已有openspec-*技能；审查不自动授权Git、真实模型、迁移或发布。

## 两仓实现基线（同步时核对）

| 范围 | 原项目Litera | 本地Litera-test |
| --- | --- | --- |
| 01/02 | 认证、私有文献库、PDF.js阅读/批注/资产/导出/进度有实现；具体验收见本仓HANDOFF | 同基础加同学模块；规范审查不重验全部业务 |
| 03/04/07 | 未合并翻译/笔记/个人模型源码；相关接口、测试、迁移、脚本按待接入处理 | 已有翻译、M:N笔记、摘录来源/搜索/定位、个人模型配置代码；启用状态与真实质量另验 |
| 05/06 | 真实提取/RAG/问答未接入 | 未接入；AI回答保存为适配/隔离Mock，不判断其他成员未合并代码的完成情况 |
| 数据库 | 源码迁移至0006_reader_assets；本轮未查/改业务数据库 | 源码迁移至0008_user_model_profiles；此前只读容器核验为MySQL0008，不是本轮新验证 |
| Compose | name:litera | name:litera-test；此本地隔离配置不回传原项目 |
| 模型/验收 | 不因同步文档宣称模型可用 | 此前快照为个人模型/Mock关闭、Vault不可用、默认模型未配置；用户历史5183验收不等于当前容器真实模型验证 |

规范正文中“现有”引用含03/04/07、notes/model相关表或工具时，只指Litera-test交付快照。原项目缺文件时先查本仓README/源码；不照抄尚未合并的verify_delivery脚本或Playwright config，不复制.env/数据卷。

## 状态、边界与维护

- **现有**是源码/测试证据，不等于部署启用、本轮执行或用户验收；**增量要求**从相关改动起遵守，**待落实**记录缺口/负责人/验证，不用文档代替实现。
- 功能场景由OpenSpec负责，八类规范约束实现方式。只改规范不创建虚假业务change，不改任务勾选/同步/归档。
- 产品看任务是否可完成；后端管契约/事务；安全管身份/机密；测试管用例/隔离/通过；运维管构建/运行/恢复；AI管模型不确定性；数据管结构/生命周期；评审管何时由谁确认完成。跨界引用原条目，不重复维护冲突版本。
- 既有合并层、DTO成功响应、动作端点、保护性downgrade等保留书面例外，不为规范任务重构。新改动违规记录条目/位置/期望/实际/证据；安全红线不以例外放行。
- 检查入口见4-测试及8-评审规范，测试/运维/AI真实验证仍按权限和环境执行；当前无覆盖全部层次的一键门禁、全链路JSON日志、完整告警/备份留存/质量评测/成本账本，不冒充已实现。
- 证据摘要使用各仓HANDOFF/已有docs/development，不恢复已删除的verification.md。用户未授权不commit/push/merge。

## 课程来源

首次审查优先读取Litera-test根目录保存的《小组项目启动 · 第7课 · 实现教程.html》；本轮不将课程HTML、附件或ZIP同步到原仓库。可访问的公共依据：

- [课程总览](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/index.html)、[规则与技能](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/rules.html)、[完整样例索引](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/case-files.html)。
- 三类基础明细：[产品](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-product.html)、[后端](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-backend.html)、[安全](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-security.html)。
- 同学五类明细：[测试](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-testing.html)、[运维](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-ops.html)、[AI](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-ai.html)、[数据](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-data.html)、[评审](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-review.html)。

采用“具体约束+检查动作”、常驻规则与重复流程的分工，按Litera技术栈适配，不照抄Go/班级角色/JWT/Qdrant、统一成功包络或不存在的make check。
