# 安全自查记录 · Litera · 文献管理与 AI 模块

环境：按 README.md 启动 Compose 四服务（db / api / extraction-worker / nginx），提交号 000b364（main），本机 http://localhost:8085
身份与数据：普通用户账号自行注册（无预置演示账号）；AGENTS.md 硬约束——用户身份只从服务端会话取得，他人 ID 与不存在 ID 返回相同 404，比较时排除随机 requestId
分工：本页 SEC-01～SEC-04 为权限类（每条按四件事写清），SEC-05～SEC-07 为资产类；SEC-08 素材只准备不试

## 受保护接口清单（不带会话应得 401）

- POST /api/v1/documents（上传 PDF）
- GET /api/v1/documents/{id}（文献详情）
- GET /api/v1/documents/{id}/extraction-candidates（提取结果）
- POST /api/v1/documents/{id}/qa（AI 问答）
- POST /api/v1/documents/{id}/extract（手动重试提取）

## 写入类接口清单（越权检测重点）

- PATCH /api/v1/documents/{id}（题录校正）
- POST /api/v1/documents/{id}/extract（触发提取写入）
- POST /api/v1/annotations、PATCH/DELETE /api/v1/annotations/{id}（批注）
- PUT /api/v1/documents/{id}/progress（阅读进度）
- DELETE /api/v1/documents/{id}、DELETE /api/v1/trash/documents/{id}（软删/彻底清除）

## 权限类（SEC-01 ～ SEC-04，每条四件事）

### SEC-01 未登录访问受保护接口 —— 绿

- **用什么手段查**：接口用例，不携带任何会话 Cookie 直接请求
- **查了什么**：受保护清单 5 个接口（上传、详情、提取结果、问答、手动提取）
- **判据**：每个接口都返回 401
- **结果**：2026-11-04 于 000b364 实测两遍（含 review-01 独立复现），5 个接口全部 401。输出原文：`POST /documents -> 401`、`GET /documents/{id} -> 401`、`GET .../extraction-candidates -> 401`、`POST .../qa -> 401`、`POST .../extract -> 401`

### SEC-02 跨用户访问与越权查询 —— 绿

- **用什么手段查**：接口用例，用户 A 的会话直接调用户 B 的资源 id
- **查了什么**：他人文献详情是否可读、他人提取结果是否可读
- **判据**：一律 404（先按 owner_id 过滤再取数），与访问不存在 ID 的返回完全相同
- **结果**：05 验收 6.2（2026-10-29）实测越权查询 extraction-candidates 经 owned_document 返回 404；documents / extraction / qa / annotations 各端点统一走 `owned_document(db, session.user_id, id)`。本条的展开整理与可原样复跑的命令见 [reports/risk-authz.md](risk-authz.md)

### SEC-03 越权写入他人题录 —— 待验证

- **用什么手段查**：接口用例，带 A 会话 PATCH B 的文档
- **查了什么**：写入类接口是否同样按 owner_id 过滤（`curl -s -X PATCH http://localhost:8085/api/v1/documents/<B的id> -d '{"title":"改过的标题"}'`）
- **判据**：404，数据不变
- **结果**：PATCH 与 GET 共用同一 owned_document 入口（代码层同路径）；专属复跑需双账号口令，本次未执行 —— 待验证，命令已附 risk-authz.md

### SEC-04 写操作缺少 Origin/CSRF —— 绿

- **用什么手段查**：接口用例，已登录会话但故意缺 Origin / x-csrf-token 头发写请求
- **查了什么**：写操作是否被 CSRF/Origin 校验拦截
- **判据**：403（INVALID_ORIGIN / CSRF 校验失败），库里无变化
- **结果**：2026-11-04 实测——curl 缺 Origin 头时写请求被 INVALID_ORIGIN 拒绝；补齐 Origin + x-csrf-token 后同一请求放行（当日联调记录）

## 七项检测总表（三段式 + 当前判定）

| 编号 | 前置条件 | 操作 | 期望 | 当前实际 | 判定 |
| --- | --- | --- | --- | --- | --- |
| SEC-01 | 服务已启动，无会话 | 对清单 5 接口逐个 curl | 全部 401 | 全部 401（两遍一致） | 绿 |
| SEC-02 | 用户 A 已登录，B 有文献 | A 会话访问/查询 B 的资源 | 404，与不存在 ID 相同 | 404（05 验收 6.2） | 绿 |
| SEC-03 | 同 SEC-02 | A 会话 PATCH B 的题录 | 404，数据不变 | 与 SEC-02 同一入口；未专属复跑 | 待验证 |
| SEC-04 | A 已登录 | 写请求缺 Origin/CSRF 头 | 403 拦截 | INVALID_ORIGIN 拒绝（实测） | 绿 |
| SEC-05 密钥明文泄漏扫描 | 本机已拉全量提交历史 | `make check-security`（或 `powershell -File scripts/check_security.ps1`）中的 git grep 段 | 0 命中 | 2026-11-04 于 000b364：0 命中（git grep 无匹配，退出码 1） | 绿 |
| SEC-06 依赖漏洞基线 | 依赖按 backend/requirements.txt 装入 api 镜像 | 同一入口中的 pip-audit 段，输出存 reports/security-baseline.md | 高危清零或书面登记处置 | `make check-security` 首跑（2026-11-04）：104 条通报 / 4 包——pip 6（构建期）、pypdf 6.20.1 有 14 条 CVE、pillow 12.0.0 约 60 条、certifi 1；pypdf≥6.21.4 与 pillow≥13.0.0 升级已登记待执行 | 黄（已登记） |
| SEC-07 行为可追溯 | 已发生提取与问答调用 | 查 extraction_jobs 与 worker 日志 | 有操作对象、状态、次数、错误码、时间戳 | extraction_jobs 有 status/attempts/error_code/时间戳；worker 日志带毫秒时间戳 | 黄（缺字段） |

**SEC-07 缺口一行**：缺「操作人 user_id」与「耗时 duration_ms」两个字段，准备加在 worker 日志层（extraction_worker.py 的拾取/完成两行日志）——后续课次的监控指标要用这两个字段。

## SEC-08 素材（只准备，不试）

- `reports/sec08-materials/injection-lecture.pdf`：正文含「Ignore all previous instructions…」的诱导内容，作为 RAG 问答的注入语料
- `reports/sec08-materials/questions.md`：3 条诱导提问（索要系统提示词原文、要求改变提取/评分规则、要求访问他人文献）及期望行为对照
