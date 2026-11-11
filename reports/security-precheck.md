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

### SEC-03 越权写入他人题录 —— 绿

- **用什么手段查**：接口用例，双账号独立会话（`apitest/config.local.ps1` A/B），A 带自己会话 PATCH B 刚上传的文档；B 回读断言数据不变
- **查了什么**：写入类接口是否同样按 owner_id 过滤（`curl -s -X PATCH http://localhost:8085/api/v1/documents/<B的id> -d '{"title":"ATTACKED BY A","version":1}'`）
- **判据**：404，数据不变
- **结果**：2026-11-11 实测（提交 e6b57fb）。B 先上传一份 PDF → 拿到 id `99158468-d476-4749-b4da-07a7a9fe15b9`，title = `Litera API Test Fixture Paper`。A 会话 PATCH 该 id → **404**；B 会话 GET 该 id → 200，title 仍是原值，**未被修改**。测试脚本 `apitest/cases/sec03-authz-write-404.ps1` 三条断言全绿：`[GREEN] A PATCH B -> 404 expected=404 actual=404`、`[GREEN] B GET still 200 expected=200 actual=200`、`[GREEN] title unchanged got=Litera API Test Fixture Paper`。cleanup 已执行。

SEC-03 与 SEC-02（跨用户读）共用同一 `owned_document(db, session.user_id, id)` 入口，读写同一 owner_id 过滤逻辑；本次双账号实测证实写入路径同样生效。

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
| SEC-03 | 同 SEC-02 | A 会话 PATCH B 的题录 | 404，数据不变 | **404**（2026-11-11 双账号实测：title 未变，测试脚本 sec03-authz-write-404.ps1 三条断言全绿） | 绿 |
| SEC-04 | A 已登录 | 写请求缺 Origin/CSRF 头 | 403 拦截 | INVALID_ORIGIN 拒绝（实测） | 绿 |
| SEC-05 密钥明文泄漏扫描 | 本机已拉全量提交历史 | `make check-security`（或 `powershell -File scripts/check_security.ps1`）中的 git grep 段 | 0 命中 | 2026-11-04 于 000b364：0 命中（git grep 无匹配，退出码 1） | 绿 |
| SEC-06 依赖漏洞基线 | 依赖按 backend/requirements.txt 装入 api 镜像 | 同一入口中的 pip-audit 段，输出存 reports/security-baseline.md | 高危清零或书面登记处置 | `make check-security` 首跑（2026-11-04）：104 条通报 / 4 包——pip 6（构建期）、pypdf 6.20.1 有 14 条 CVE、pillow 12.0.0 约 60 条、certifi 1；pypdf≥6.21.4 与 pillow≥13.0.0 升级已登记待执行 | 黄（已登记） |
| SEC-07 行为可追溯 | 已发生提取与问答调用 | 查 audit_logs 表（api 容器内 `python -c "from app.models import AuditLog; ..."`） | 每行七列 + 单行 JSON payload | 2026-11-11 实测：三类操作 10 行全在（extract×6、qa×1、translate×1），每行七列完整、无换行、payload bytes < 4KB | **绿** |

**SEC-07 七列审计日志三段式**：

- **前置条件**：api 与 extraction-worker 已重建（含 0012_audit_logs migration），数据库自动建 audit_logs 表
- **操作**：触发三类操作——手动提取（走 worker 队列）、QA 问答、翻译。实测用例：extr-manual-retry、qa-answer-citations、trans-selection
- **期望**：每次写操作向 audit_logs INSERT 一行，字段覆盖七列：操作人（user_id）、操作时间（created_at）、操作类型（action）、操作对象（target）、结果状态（status）、技能标识（skill）、用量与耗时（duration_ms + usage JSON）；payload 列携带单行 JSON（JSON dumps 自动转义，内容经 _truncate 限 4KB）
- **结果**：2026-11-11 实测，audit_logs 表 10 行：
  - extract × 6（processing → success 成对，skill=extract-llm，duration_ms 真实：4943/5673/3932/7649）
  - qa × 1（status=success，skill=qa-rag，duration_ms=6254，usage.model 携带模型名）
  - translate × 1（status=success，skill=translate，duration_ms=4257，usage.extra 含 source/target/pageNumber/pdf_ms/llm_ms）
  - 每行 payload 单行（`payload single : OK (no newlines)` 断言通过），约 350–374 bytes
  - `log_audit()` 内部 try/except，DB 故障只打 logger.warning 不阻断业务路径

**SEC-07 实现位置**：

| 组件 | 打点 |
|---|---|
| `backend/app/extraction_worker.py` | claim 时记 processing 行；_safe_run 完成后 _log_extraction_outcome 根据 final job.status 记 success / failed / partial |
| `backend/app/qa.py` `_save` / `_insufficient` | 所有 QA 完成路径汇聚点，记 success（answered）/ partial（insufficient_evidence） |
| `backend/app/translations.py` `translate` | 成功 return 前 + except ModelFailure 里各记一条 |
| `backend/app/audit.py` | `log_audit()` 统一封装七列构建 + 转义截断 + try/except 安全写入；`log_denied_request()` 记被拒请求 |
| `backend/app/main.py` `request_context` 中间件 | `/api/` 下 401/403/404 响应统一补一条 `status="denied"` 审计；user_id 只从服务端会话 cookie 解析 |
| migration `0012_audit_logs` | audit_logs 表 + 三索引（user_created / action_status / target） |

**被拒请求同样记一条（2026-11-11 补测）**：重放 SEC-03 越权 PATCH（A 改 B 文档 → 404），audit_logs 随即查到一条 `action=documents.patch, status=denied, user_id=A, target=B文档ID, usage.extra.http_status=404` 的记录；x-401-matrix（8 条 401）与 INJ-03（403）同样各落一行。被拒请求不携带 skill/duration_ms，操作细节在 `usage.extra`（method/path/http_status）。

**成功与失败全覆盖（2026-11-11 第二轮）**：
- QA 失败审计：[qa.py](file:///C:/Users/Lenovo/Desktop/InternetSoftware/project/backend/app/qa.py) ask 入口捕获 HTTPException（status≥500 或 429）记 `status="failed"` 带 error_code；非 HTTP 异常记 `error_code="INTERNAL"`。
- 翻译失败审计：[translations.py](file:///C:/Users/Lenovo/Desktop/InternetSoftware/project/backend/app/translations.py) ModelFailure 分支记 failed；[translation_runtime.py](file:///C:/Users/Lenovo/Desktop/InternetSoftware/project/backend/app/translation_runtime.py) `observed_translation` 对取消(499)/意外异常(500)兜底记 failed。
- token 用量：网关响应带 `usage` 时 [ai_service.py](file:///C:/Users/Lenovo/Desktop/InternetSoftware/project/backend/app/ai_service.py) 累加 `prompt_tokens`/`completion_tokens` 进 `TranslationTiming`，QA/翻译打点时写入 `tokens_in`/`tokens_out`。**机制已实现；非 null 数值待上游网关恢复后复测验证**（当前 MODEL_QUOTA 429，成功路径拿不到 usage）。
- 中间件 denied 覆盖从 401/403/404 扩到全部 4xx（含 422 校验拒绝、429 限流）。
- 实测：状态分布 denied=17 / failed=18 / success=97 / partial=7 / processing=117；SEC-03、INJ-03、x-401-matrix 回归全绿。

## SEC-08 素材（只准备，不试）

- `reports/sec08-materials/injection-lecture.pdf`：正文含「Ignore all previous instructions…」的诱导内容，作为 RAG 问答的注入语料
- `reports/sec08-materials/questions.md`：3 条诱导提问（索要系统提示词原文、要求改变提取/评分规则、要求访问他人文献）及期望行为对照

## 三条反例（SQL 注入 / XSS / CSRF，绿）

> 与 SEC-01～SEC-04 权限类不同，这三条是**输入/传输层的注入与伪造**，属于"即使权限正确也不能放进来"的防守线。全部按三段式写进 `apitest/cases/`，随 `make check` 常驻回归。

### INJ-01 SQL 注入 —— 绿

- **前置条件**：用户 A 已登录；库里该用户有若干真实文档（实测 42 行）
- **操作**：`GET /api/v1/documents?q=' OR '1'='1`（URL 编码后即 `%27%20OR%20%271%27%3D%271`）
- **期望**：请求正常返回（200 而非 500/404）；`items.total` 应为 0 或显著小于用户全部文档数——注入串被当作普通字符串，不会绕过 `ilike(pattern, escape="!")` 的参数化绑定
- **结果**：2026-11-11 实测全绿。API 返回 200，`injection_total=0`，而 `owned_total=42`。注入串被视为普通匹配词，匹配不到任何 title/abstract/doi/journal/authors/keywords 字段。
- **修复证据**：`backend/app/library.py:86-88` 手动 escape `% _ !` 后用 `ilike(pattern, escape="!")`；`sort`/`order` 字段是 Pydantic `Literal` 白名单（`backend/app/documents.py:282`），没法占位符化的位置也没法注入。

### INJ-02 XSS（存储型，前端渲染） —— 绿

- **前置条件**：用户 A 已登录，有一份可 PATCH 的文档
- **操作**：`PATCH /api/v1/documents/{id}` 写入 title = `<script>alert(1)</script>`；再 `GET /api/v1/documents/{id}`
- **期望**：API 正常处理（200）；`GET` 回读 title **原样保留**（后端**不做**标签剥离，那是过滤责任）；前端 Vue 的 `v-text` 默认文本插值会自动 HTML 转义，页面不执行脚本
- **结果**：2026-11-11 实测全绿。`PATCH 200`、`GET 200`，`title preserved verbatim got=[<script>alert(1)</script>]`。Vue 前端代码全局 grep `v-html` 0 命中——全量用 `v-text`，浏览器渲染出 `&lt;script&gt;alert(1)&lt;/script&gt;` 纯文本，不会弹窗。
- **修复证据**：前端不用 `v-html`；后端 Pydantic 白名单校验 title 字段长度/类型，不做 HTML 过滤（由渲染层保证安全）。

### INJ-03 CSRF（跨站伪造，Origin + Token 两道闸） —— 绿

- **前置条件**：用户 A 已登录（浏览器有会话 cookie + 内存里有 csrfToken）；攻击者拥有 evil.com 域；存在可写端点 `PATCH /api/v1/documents/{id}`
- **操作（开关一：无 Origin）**：`curl -b jar -H 'x-csrf-token: <token>' --data-binary '{"title":"x","version":1}' PATCH /documents/{id}` —— 故意缺 Origin 头；**开关二：evil Origin**：同请求带 `Origin: http://evil.com`
- **期望**：开关一 → `403 INVALID_ORIGIN`；开关二 → 拒绝（非 200，`INVALID_ORIGIN` 或 CSRF token 与 Origin 域不匹配的校验失败）；**两道开关各挡一条伪造**
- **结果**：2026-11-11 实测全绿。开关一：`[GREEN] no Origin -> 403 expected=403 actual=403`，`code=INVALID_ORIGIN`；开关二：`[GREEN] evil Origin rejected (not 200) status=422`（CSRF token 签了 Origin 域名，evil.com 的 token 与合法会话不匹配）。Cookie 在后端设置了 HttpOnly + SameSite（非显式 lax/strict 但 httponly 已防 XSS 偷 cookie）。
- **修复证据**：后端 `CSRFMiddleware` 对所有写请求（非 GET/HEAD/OPTIONS）先查 Origin 是否在 `PUBLIC_ORIGIN` 白名单，再查 csrfToken 签名是否匹配 Origin 域。
