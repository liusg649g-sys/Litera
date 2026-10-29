# 8-Litera 评审与完成定义规范

> 跨仓适用说明：规范约束两仓后续开发，本文实现快照来自Litera-test。原Litera目前仅01/02、迁移至0006；03/04/07及0007/0008尚未合并，相关“现有”描述只属于Litera-test，在原项目按待接入要求理解。文件同步不等于代码、脚本或部署已合并，先查本仓实际文件；总表见[规范索引](README.md)。

适用：功能、接口、数据、规范及交付变更。依据第7课[评审规范](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-review.html)和[完整样例](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/case-review.html)。2026-10-28按当前仓库修订；文档命令和时限不是执行授权。

## 1. 总则与角色

自动化/静态检查与用户功能/UI验收分别记录，不互相替代；适用检查共同满足才完成。文档改动不强制重跑全部业务测试/用户验收。未测、跳过、Mock、SQLite、MySQL和真实浏览器环境分别注明。

当前OpenSpec路径为`openspec/changes/<完整change名>/{proposal.md,design.md,specs/<capability>/spec.md,tasks.md}`；Requirement/Scenario在specs，不在proposal；任务与场景可多对多映射，勾选不证明行为。

| 评审者 | 职责与输出 |
| --- | --- |
| 模块负责人 | 范围、接口/迁移、非目标、消费者、自检证据 |
| 另一名成员 | 场景、授权、业务影响交叉评审；明确通过/修改/待验证 |
| Harness/助手 | 规范一致性、事实、引用、遗漏；不代替用户反馈或擅自批准合并 |
| 工具 | 实际命令/环境/退出码；格式化与测试各自检查，不混淆OpenSpec能力 |
| 用户 | 适用功能/UI的明确反馈，沉默不算通过 |

当前CI、钩子和统一一键门禁未全部实现；以下是增量协作约束，不宣称已自动强制。常驻入口见[AGENTS.md](../../AGENTS.md)。

## 2. 八项规范条目

### 2.1 完成定义（R01）

| 项 | 判定 | 未通过/待验证表现 |
| --- | --- | --- |
| 场景与范围 | 适用specs场景满足，有任务/证据映射；纯文档注明无业务change | 仅任务勾选或截图 |
| 检查结果 | 按§3执行受影响检查，结果可重现 | 失败、关键测试无解释跳过、Mock当真实模型 |
| 数据兼容 | 涉及结构/文件时验证隔离升级、重复head、保留数据和回退策略 | 强行降级保护性迁移；SQLite冒充MySQL |
| 文档同步 | 字典/DTO/页面/规范/README/HANDOFF按实际变化一致 | 新语义缺失、历史状态冒充当前 |
| 副本一致性 | 涉及跨存储时验证失败/重试、所有副本及独立笔记语义 | 原件误删、残留未登记、202当完成 |
| 证据归档 | 按change/阶段找到范围、命令/环境、评审、边界 | 只有聊天无归档 |
| 用户验收 | 用户可见行为在约定环境明确通过；文档任务不适用时说明 | 沉默/期限/模拟结论当同意 |

MySQL专项未齐只能标部分交付/待验证，不能称整个change完整验证。无相关改动的检查可说明不适用，不为文档审查触发业务库或真实模型操作。

### 2.2 规模与合并策略（R02）

- 一次变更聚焦一组共同验证的任务；约30个源文件为新增审查提示阈值，超出说明拆分方案或跨模块原子交付理由，不拆成缺接口的半成品。
- 评审范围使用PR base到head或当前未提交diff，不固定以HEAD~1代表整份PR。标题写问题/行为及change/阶段，文档不硬套P3编号。
- 默认经另一成员明确评审、适用检查通过及用户授权才合并；无授权不commit/push/merge，不强推覆盖他人，不因超时自行合并。
- 历史P1/P2/P3仅是交付划分；03/04/07可合理原子交付，不禁止所有跨阶段PR。

**检查**：范围可理解/验证、生产者消费者齐全、拆分不破坏契约；记录合并方式/授权，不假报已有主干保护。

### 2.3 评审检查表（R03）

| 层面 | 检查内容 |
| --- | --- |
| 规约 | 目标/非目标、前置→操作→结果、正常/失败/边界/越权、生产者/消费者 |
| 产品/后端/安全 | P01–P10、B01–B12、S01–S14适用项，引用原规范，不另写相反规则 |
| 数据 | [D01–D09](7-data-specification.md)：真实字段/归属、迁移保护、上传/清理顺序、敏感分级和副本 |
| 证据 | 工具真实检查边界、失败/跳过原因、实际/Mock环境；不改断言/门槛来变绿 |

现有会话写操作须Origin/CSRF，不能把“current_session或require_csrf”当充分条件；注册/登录使用Origin+限流，不要求已有会话，见[授权清单](3-security.md#授权清单与核对方法)。

OpenSpec strict检查规约结构/语义；本地链接、文档事实、任务—场景映射另核查。`git diff --check`不是通用Markdown/业务验证器。

### 2.4 责任人与时限（R04）

新增协作目标：交叉评审1个工作日内响应；超时提醒并组内协调/重新指定审查人，不默认Approve。用户验收时间在部署通知约定，未回复记待验收，不假设功能可接受。

01/02负责人Jensen Zhang，03/04 Siguo Liu，05/06 Jialu Ma；07为03/04配套，跨模块共同审阅。每次另指定具体评审人，不代签姓名/日期。归档/发布/Git动作仍需授权。

### 2.5 门禁必跑（R05）

按范围选择§3的适用检查，任一规定检查失败不得宣称通过；依赖不可用记待验证。不得降低门槛/删断言。当前不存在test:auth/translation/notes/unified/user-models等npm script，使用已有config或verify_delivery入口。

平台专项/私有fixture opt-in跳过须解释影响，不一概要求0跳过，也不把跳过计为通过。SQLite不替代MySQL，Mock不替代真实QA/模型。

### 2.6 例外书面化（R06）

记录条目ID、原因、范围、风险/替代措施、申请人、明确评审人/结论、复查/到期条件与证据。未审查写待确认；机密/授权红线不可豁免。

| 事实/候选 | 处置 |
| --- | --- |
| 0005/0006/0007拒绝破坏性降级，0008有配置拒绝drop | 源码保护行为；验证拒绝/兼容退应用，不强求降级成功 |
| PDF上传孤儿文件全量对账未实现 | 待落实缺口，沿D08说明；不编造批准人/日期 |
| MySQL专项证据未齐 | 仅部分交付/待验证，不自动豁免归档条件 |
| 合并层、DTO成功响应、动作端点 | 引用2-backend的兼容例外，不复制另一套 |

原稿EX-001～004未找到可核实的署名批准依据，不作为有效批准记录；改密码无迁移也不是授权规则例外。后续申请由实际负责人补证。

### 2.7 证据归档（R07）

- 字段语义见[数据模型](../design/data-model.md)，当前表索引见[7-数据规范](7-data-specification.md#4-当前数据字典索引)，API见design/delivery对应文档，不引用不存在的docs/design/data-specification.md。
- 开发/修复证据放docs/development，交付材料放docs/delivery；规范审查摘要可追加HANDOFF，README链接到证据，不另建重复核验文件。不要求每次文档改动都生成PR描述/manifest。
- 证据含范围、改动、命令/环境/退出码、失败/跳过原因、实际用户反馈及来源、未测/Mock边界与回退影响；不提交私有PDF/Key/数据库。
- 提交信息可用Change/Verify/Evidence字段，值须真实可查；仅定义格式不授权提交。

### 2.8 复盘留痕（R08）

记录触发、根因、修正和复测；未归档阶段可追加带日期修复记录，已归档内容以新记录/勘误引用，不悄改历史。不必等下一阶段才记录当前问题。

**检查**：按change/阶段找到实际/期望、根因、处置和验证；历史用户反馈不当当前验收。

## 3. 当前可用检查入口

先安装锁定依赖，Python使用相应依赖环境。以下是后续检查入口，不代表本次全部执行。

| 范围 | 目录/命令 | 前提与判定 |
| --- | --- | --- |
| 文档 | 根：`git diff --check`，另核对本地链接/事实/编号 | 不启动服务；本次适用 |
| 规约 | 根：`openspec validate <完整change名> --strict --no-interactive` | 相关OpenSpec变动才执行；help核对，不代替行为/链接审查 |
| 隔离后端 | 根：`python scripts/verify_delivery.py backend` | 临时SQLite/PDF/覆盖配置/阻断外网；可带目标test文件名 |
| 前端单测 | 根：`python scripts/verify_delivery.py frontend` | frontend依赖已装，Vitest |
| 类型/构建 | 根：`python scripts/verify_delivery.py build` | 包含types，输出.cache而非在线dist，脚本有磁盘保护 |
| 浏览器 | 根：`python scripts/verify_delivery.py browser notes`，可选translation/captures/user-models/unified | 先独立build并安装浏览器；临时库/替身模型 |
| 文献库/阅读器 | frontend：`npm run test:library`、`npm run test:reader` | 已有config，先查测试Python/端口，不指向业务实例 |
| MySQL | 独立测试实例核对URL/PDF根后按conftest运行选定pytest/迁移 | 专用litera_test会清表；不自动drop库或触碰业务库 |

直接Playwright可在frontend执行`npx playwright test --config=playwright.notes.config.ts`等真实config；认证默认config另查baseURL。不使用`python -m scripts.verify_delivery.py`，verify_delivery不是OpenSpec验证器。

归档/同步复用openspec-sync-specs、openspec-archive-change技能并核对本地CLI，不照抄不存在的sync-specs/archive-change子命令。本次不归档。

历史5177/5180/5183不是每人必有环境；当前本地Compose入口为litera-test的localhost:8080，运行状态另查。启动/迁移/在线构建/删除按当前授权执行，历史“不运行Docker”不是永久禁令，也不是改数据许可。

规则/AGENTS/技能/门禁脚本/CI/钩子/OpenSpec变动需说明改什么、为什么、如何验证并交叉评审，不能助手自行降低检查。

## 4. 合规检查清单

- [ ] R01：范围/场景/证据齐，未实现、未配置、未验证、Mock分开。
- [ ] R02：范围聚焦；超提示阈值有说明，合并策略/授权明确。
- [ ] R03：人工/Harness/工具边界明确，授权不止“有会话”。
- [ ] R04：实际审查人和响应目标明确，超时/沉默不算批准。
- [ ] R05：适用的真实入口通过，跳过有理由，不对业务库无条件降级。
- [ ] R06：例外有证据与复查条件，不代签他人。
- [ ] R07：文档/字典/DTO同步，证据存在且无机密。
- [ ] R08：问题及复测可追溯，不改写历史结论。

本次仅审订文档事实/流程及编号，未执行合并、迁移、归档、删除演练、真实模型调用或用户验收。
