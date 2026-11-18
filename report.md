# 项目报告 · Litera · 第 ? 组

- 项目：Litera——文献管理、PDF 阅读与 AI 辅助阅读系统
- 成员与分工：
  - 马嘉璐（实现功能：题录异步提取、AI 问答，写`apitest/cases/` 接口用例、七类核查表和`Makefile` 两个门禁目标）
  - 张钧剑（功能实现：文献管理、PDF 阅读器，八类工程规范，评审记录和压测数据）
  - 刘思果（实现功能：翻译与笔记，做风险与交付——写并发/事务/权限三份三查记录）
- 仓库地址：`https://github.com/liusg649g-sys/Litera`
- 使用的 Harness：Trae、
- 支撑记录目录：`reports/`（交叉评审、安全自查、依赖基线与高风险三查）
- 演示视频下载地址：`<待填：录屏上传网盘后的分享链接>`
- 提交日期：2026-12-8

## 1 一句话介绍

Litera 面向个人研究者，解决读外文文献时"翻译、批注、回找原文出处分散在多个工具"的问题：上传 PDF 后在同一个阅读器里完成选区翻译、原文定位批注与基于原文片段的问答，每个账号的文献、译文与笔记互不可见。

## 2 AI 用了在哪

全部业务代码与 OpenSpec 规约由 AI 生成；下面列出代码与规约之外的 AI 产出：

| # | 交付物 | 仓库位置 | 本项目的内容与证据 |
|---|---|---|---|
| 1 | 规则文件 | `AGENTS.md`；`docs/standards/README.md` | `AGENTS.md` 全文含第 3 节「AI 生成代码核查清单」：七类核查问题与检查手段、命名与提交约定；详细规范仍由 `docs/standards/1-product.md`～`8-review-specification.md` 维护。 |
| 2 | 接口用例 | `apitest/cases/`（34 条）、`apitest/lib/common.ps1`、`apitest/run_checks.ps1` | 幂等：`extr-duplicate.ps1` 同一 PDF 连续投递两次只保留一个 `extraction_jobs` 行并返回 409 `DUPLICATE_DOCUMENT`，`docs-upload-duplicate-409.ps1` 覆盖上传层；跨用户 404：`sec03-authz-write-404.ps1` 中 A 改 B 的文献返回 404 且标题不变，`docs-authz-matrix.ps1` 覆盖嵌套资源；非法参数 400：`x-invalid-param-400.ps1` 断言错误旧密码 `INVALID_CURRENT_PASSWORD`、新旧密码相同 `PASSWORD_UNCHANGED`，Pydantic 字段校验另由 422 反例覆盖。 |
| 3 | 评审记录初稿 | `reports/review-01.md`～`review-04.md` | `review-01` 人工交叉评审 SEC-01/SEC-05；`review-02` 依赖审计由 104 条降至 12 条；`review-03` 注入自审，记录 INJ-03 判据由“必须 403”改为“非 200”；`review-04` 幂等与并发自审。`review-01` 已定稿，02～04 为初稿，待人工复核。 |
| 4 | 高风险三查记录 | `reports/risk-concurrency.md`、`risk-transaction.md`、`risk-authz.md` | 并发：重复提交 + 20 份变体，队列 `completed=32`、`queued=0`，无重复任务行；事务：`create_extraction_job` 到 `persist_extraction` 仅一次 commit，worker 停止/恢复与崩溃恢复均只更新原行；权限：A 访问 B 与不存在 ID 同为 404，无会话 401。 |
| 5 | 压测脚本与报告 | `reports/bench.md`、`apitest/cases/extr-p95-concurrency.ps1` | 现有门禁为 20 次上传，P95=0.200s、MAX=0.203s，队列 300s 内排空；N+1 门禁 50 行列表 4 条 SELECT。k6 目标参数已记录为 `vus=20`、`duration=60s`，但 k6 脚本与返工前 P95 基线尚未落盘，报告如实标注，不用推测值补齐。 |
| 6 | 验证命令编排 | `Makefile`、`scripts/check_all.ps1`、`scripts/check_security.ps1`、`scripts/check_scenarios.py` | `make check` 依次跑公共函数、数据库、场景追溯，再跑真实 Compose 接口用例并按类别汇总；`make check-security` 跑 SEC-05 密钥、SEC-06 `pip-audit`、SEC-07 前端转义和 5 条动态反例；退出码 0/1/2。 |
| 7 | README | `README.md`、`apitest/README.md` | 环境准备（`backend/.venv`、`requirements-dev.txt`）、启动 Compose、`make check`/`make check-security`、退出码、`config.local.ps1` 测试账号与报告位置。 |

使用的 Harness：Trae、

七类核查问题与检查手段落在 `AGENTS.md` 第 3 节：

| 类 | 核查问题 | 本项目检查手段 |
|---|---|---|
| 接口入口 | 参数校验、状态码、统一 error 包络是否齐 | `apitest/cases` 34 条用例 + 参数断言（未登录 401、跨用户 404、非法参数 400/422） |
| 业务逻辑 | 状态流转与分支是否符合规约场景 | AI 自审对照 `openspec/changes/*/specs/*/spec.md` 场景 + `scripts/check_scenarios.py` 追溯 7 个 change、263 个场景 + 脚本场景用例 |
| 数据库 | 迁移可执行、事务边界、索引是否齐 | `backend/tests/test_migrations_gate.py`（迁移链、重复 head、模型声明索引、回滚拒绝并保留核心行）+ 既有迁移用例 + 单事务 commit 核对（`reports/risk-transaction.md`） |
| 公共函数 | 空值、边界与异常路径是否处理 | `backend/tests/` 单元测试 + `pytest-cov` 覆盖率门禁（默认 80%，本轮 472 passed、覆盖率 82.96%） |
| 错误处理 | 错误码、重试与降级路径是否完整 | `test_audit_outcomes.py` 核对 success/failed/denied 审计行 + 故障注入用例（`extr-manual-retry.ps1`、`extr-stop-start.ps1`） |
| 安全 | 越权、注入、密钥与依赖 | `make check-security`：SEC-05/06/07 + 动态反例 `sec03-authz-write-404.ps1`、`inj01`～`inj03`、`qa-injection.ps1` |
| 性能 | N+1、慢语句、重复投递与并发提交 | `test_query_performance.py`（50 行列表 ≤12 条 SELECT、单语句 ≤100ms，实测 4 条）+ `extr-p95-concurrency.ps1`（P95≤0.5s、MAX≤2.0s，实测 0.200s/0.203s）+ `reports/bench.md` |

## 3 审核记录

| # | 用什么手段查 | 查了什么 | 怎么判的 | 结果 |
|---|---|---|---|---|
| 1 | 人工 · 交叉评审（独立会话复现，不复读原结论） | SEC-01（未登录访问 5 个受保护接口）与 SEC-05（密钥明文扫描），提交号 `000b364` | 5 个接口全 401、`git grep` 0 命中（退出码 1）才判一致 | 两条复现值与原记录一致，判定通过。记录：`reports/review-01.md` |
| 2 | 脚本 `make check-security`（pip-audit + 密钥扫描） | 运行期依赖的已知漏洞通报 | 高危须清零，或以可复查条目登记（包名、漏洞编号、暂不修理由、降险措施） | 初测 104 条通报（4 包）→ 升级 certifi/pypdf/Pillow 后 12 条，剩余全为构建期 `pip`，登记为条目并写明 4 条降险措施。记录：`reports/review-02.md`、`reports/security-baseline.md` |
| 3 | AI 自审 + 脚本反例 | 注入类三条：SQL 注入搜索、标题 XSS、CSRF 伪造 Origin | 注入参数须返回空结果；前端 `v-html` 0 命中；伪造 Origin 只要非 200 即视为被拒 | 自审发现 INJ-03 首次把判据写成"必须 403"，实测返回 422（签名与 Origin 域不匹配），改判据为"非 200"并固化为用例常驻。记录：`reports/review-03.md`、`reports/security-precheck.md` |
| 4 | 脚本 `apitest/cases`（真实 Compose，双账号） | 同一 PDF 重复提交、worker 重复投递是否只出一份结果 | `extraction_jobs` 同 documentId+fileHash 仅一条生效；`extraction_results` 同版本仅一行 | 第二次提交返回 409 `DUPLICATE_DOCUMENT`；崩溃恢复后重跑只更新同一行，attempts 递增而题录不变。记录：`reports/review-04.md`、`reports/risk-concurrency.md` |

四条中三条由脚本或 AI 自审发现，第 1 条是人工交叉评审；人工只做机器给不出判据的复现确认。

## 4 高风险三查

- **并发**（脚本）：同一 PDF 连续两次提交 + worker 重试/崩溃恢复两条重复路径，断言 `extraction_jobs` 同 documentId+fileHash 仅一条生效、`extraction_results` 同版本仅一行。结果：第二次提交在 SHA-256 查重阶段即返回 409 `DUPLICATE_DOCUMENT`，不创建第二个任务；20 份变体并发上传队列排空后 `completed=32`、`queued=0`，无重复任务行。记录：`reports/risk-concurrency.md`
- **事务**（脚本 + 代码核对）：停止消费者后提交任务、恢复后是否恰好执行一次；崩溃是否留下无人处理的孤儿任务。结果：`create_extraction_job` 与 `persist_extraction` 之间只有一次 `db.commit()`（`documents.py` L216–L221）；`stop extraction-worker` 期间任务停留 `queued`，`start` 后 1s 内拾取、10s 内 `completed`，结果表仍一行；手工置 `processing` 模拟崩溃后重启，日志 `Recovered 1 interrupted job(s) back to queued` 并完成。边界如实标注：文献行先提交，不变量是"任务存在 ⇒ 结果基础行存在"，投递为 at-least-once 而非严格 exactly-once。记录：`reports/risk-transaction.md`
- **权限**（脚本）：A 账号的会话访问 B 的文献与提取结果，以及无会话访问。结果：跨用户与不存在 ID 返回同一个 404（先按 `user_id` 过滤再取数），无会话一律 401；用例 `apitest/cases/sec03-authz-write-404.ps1` 三条断言常驻。记录：`reports/risk-authz.md`

三条均由脚本复跑，人工只在设计用例时确认"要断言什么"，判据确认后固化成用例。

## 5 门禁与演示

- **准入流程**：AI 初稿 → AI 自审（`docs/standards/` 逐类过）→ 脚本门禁（`make check` / `make check-security`）→ 人工确认（只确认机器判不了的需求意图，并补规则或用例）→ 合入 `main`
- **验证命令**：`make check`（`apitest/cases` 全量跑批，最近一次 RED=0）、`make check-security`（SEC-05 通过，SEC-06 高危清零并以条目登记构建期依赖）
- **先红后绿证据**：提交 `e6b57fb`（用例对齐真实契约，10 文件 +93/−38，跑批由红转绿）；依赖审计由 104 条通报降至 12 条（`reports/dep-audit-before.txt` / `after.txt`）
- **现状**：两个门禁命令已可复跑，但**尚未接入 CI 与 `main` 分支保护**（仓库无 `.github/workflows`），此项未完成，如实列出
- **部署环境地址**：`<待填：对外可访问地址>`
- **演示四步**：`POST /api/v1/auth/login` 取会话与 CSRF → `POST /api/v1/documents` 上传 PDF → `GET /api/v1/documents/{id}` 看到 `parseStatus` 由 `processing` 转 `completed` → 换另一个账号访问该文档，返回 404

## 6 复盘

代价最大的一次返工是审计日志。第一版只在成功路径打点（问答落库、翻译成功、任务完成），自测时重放一次越权写请求，`audit_logs` 查不到任何记录——拒绝发生在 `owned_document` 与 CSRF 校验层，根本没进业务逻辑。改成在 `main.py` 的请求中间件里对 4xx 统一补一条 `denied` 行后，又发现模型失败（配额、超时）同样不留痕，再补 `qa.py` 的失败分支与 `translation_runtime.py` 的取消/异常兜底，前后三轮才做到"每种结局都有一行"，涉及 `audit.py`、`main.py`、`qa.py`、`translations.py`、`translation_runtime.py` 五个文件。根因是当初按"成功流"设计，没有先列结局清单。

下次改法：把"每个受保护端点必须有成功、失败、拒绝三类审计行"写进 `AGENTS.md`，新端点接入时按结局清单逐项过，而不是事后补。
