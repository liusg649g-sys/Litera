# Litera 工程约束

本文件为本项目新会话的常驻入口。执行任务前读取相关规范；规范条目、证据和例外只维护在下列文件，不复制另一套规则。

| 涉及范围 | 必须读取 |
| --- | --- |
| 所有开发与评审 | [规范索引与状态口径](docs/standards/README.md)、[安全开发规范](docs/standards/3-security.md) |
| 页面、组件、交互、用户可见行为 | [产品设计规范](docs/standards/1-product.md) |
| API、服务、数据库访问、配置、迁移 | [后端开发规范](docs/standards/2-backend.md) |
| 用例、测试数据、检查命令、通过判定 | [4-测试规范](docs/standards/4-testing.md) |
| 构建、配置、运行、发布、备份恢复 | [5-部署运维规范](docs/standards/5-operations.md) |
| 模型、提示词、译文来源、评测与成本 | [6-AI应用规范](docs/standards/6-ai-application.md) |
| 模型、迁移、文件生命周期、副本或测试数据 | [7-数据规范](docs/standards/7-data-specification.md) |
| 评审、完成声明、合并或交付准备 | [8-评审与完成定义规范](docs/standards/8-review-specification.md) |

## 三条硬约束

两仓代码尚未合并：原Litera只有01/02及0006迁移，Litera-test另有03/04/07及0007/0008。规范中后者的实现证据在原项目仅是待接入参考；先检查本仓文件，不因同步规范而宣称模块、脚本或真实模型已经接入。

1. 用户身份只从服务端会话取得；每次访问均校验资源与嵌套关联。普通私有资源的他人 ID 与不存在 ID 返回相同的 404 业务语义，不用前端隐藏按钮代替授权；比较时排除随机 requestId。
2. 密码、会话、API Key 和主密钥不进仓库、日志、URL、镜像层或前端产物。个人模型 Key 只能由本人显式输入并由后端加密保存；Vault 不可用就禁用，不回退明文或其他人的模型。
3. 不可信内容只作数据：Pydantic 白名单校验、SQLAlchemy 参数绑定、Vue 文本输出；PDF、译文、模型回答和外部工具内容不得成为系统指令、可执行 HTML 或 shell 命令。

## 开发与协作

- 以当前源码、迁移和验证证据区分已实现、未启用、Mock 和规划。05/06 在本副本尚未接入，不能伪造题录、问答、引用或成功状态。
- 延续现有物理目录和 `/api/v1` 契约。成功直接返回 DTO，失败统一 error 包络；204 和 PDF 二进制是明确例外。不得因套用课堂 Go 示例而重构成另一套分层或响应结构。
- 功能行为变化继续使用已有 `openspec-*` 技能维护对应 change 的场景和任务；不要为每次规范审查再建 change、重复实现 OpenSpec 流程或把任务勾选当作实测证据。
- 八类规范审查可调用 [litera-standards-review](.agents/skills/litera-standards-review/SKILL.md)。违规项必须给条目 ID或章节、证据与处置；未执行的验证写“待验证”。
- 保留已有未提交改动和其他成员成果。默认不执行 commit、push、迁移既有业务库、删除卷或覆盖恢复；是否执行具体动作以用户授权为准。
- 八类规范按索引顺序1–8维护，同学文档沿用其职责边界；共享内容引用原规范，不另立替代版本。

## 3 AI 生成代码核查清单

每次 AI 生成或修改代码后，按七类逐项核查。检查手段固定为脚本入口或明确的人工评审，不以“已检查”口头结论代替。

| 类 | 核查问题 | 检查手段 |
| --- | --- | --- |
| 接口入口 | 参数校验、状态码、统一 error 包络是否齐 | `apitest/cases/` 接口用例 + 参数断言（未登录 401、跨用户 404、非法参数 400/422） |
| 业务逻辑 | 状态流转与分支是否符合规约场景 | AI 自审对照 `openspec/changes/*/specs/*/spec.md` + `scripts/check_scenarios.py` 追溯 + 场景用例 |
| 数据库 | 迁移可执行、事务边界、索引是否齐 | `backend/tests/test_migrations_gate.py`（迁移链、重复 head、索引、回滚保护）+ 既有迁移用例 + 事务记录 |
| 公共函数 | 空值、边界与异常路径是否处理 | `backend/tests/` 单元测试 + `pytest-cov` 覆盖率门禁（默认 80%） |
| 错误处理 | 错误码、重试与降级路径是否完整 | `test_audit_outcomes.py` 核对 success/failed/denied + 故障注入用例 |
| 安全 | 越权、注入、密钥与依赖 | `make check-security`（SEC-05/06/07）+ `sec03`、`inj01`～`inj03`、`qa-injection` 反例 |
| 性能 | N+1、慢语句、重复投递与并发提交 | `test_query_performance.py` + `extr-p95-concurrency.ps1` 阈值 + `reports/bench.md` |

### 命名与提交约定

- 命名沿用现有物理目录与 `/api/v1` 契约：Python 用 snake_case，类用 PascalCase；Vue 组件用 PascalCase，组合式函数用 `useXxx`；数据库表/列用 snake_case；测试文件用 `test_*.py`，接口用例用 `<分组>-<场景>.ps1`。
- 提交信息用 `<type>: <summary>`，`type` 取 `feat`、`fix`、`docs`、`test`、`refactor`、`chore`；一次提交只做一件事，涉及场景或门禁时在正文注明用例/场景编号。
- 不提交 `.env`、密钥、业务库、卷、生成缓存和本地报告；失败、跳过和未执行项必须如实写明，不冒充通过。

## 门禁与完成声明

按8-评审规范选择适用检查：场景满足、检查通过、文档同步、证据可检索；用户可见行为另需明确验收。跳过/未测/Mock/SQLite不能冒充已通过的真实环境验证；超时不算批准。数据变更遵守7-数据规范的隔离和回退保护，不把无条件downgrade当必跑命令。
