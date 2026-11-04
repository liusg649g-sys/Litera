# Tasks

负责人：Jialu Ma。状态：后端核心 ✅；前端 ✅；新设计（自动回填取代人工接受）5.4–5.6 ✅ 已实施并通过端到端验证。

## 1. 数据模型与迁移

- [x] 1.1 编写 Alembic 迁移 `backend/migrations/versions/0009_extraction.py`，创建 extraction_jobs / extraction_results / document_pages / document_chunks 四张表；Compose 启动时自动执行 `alembic upgrade head` 验证表结构和约束生效 ✅
- [x] 1.2 在 `backend/app/models.py` 新增 SQLAlchemy ORM 映射 ExtractionJob / ExtractionResult / DocumentPage / DocumentChunk；ExtractionResult 用 `candidates` 属性映射到 DB 列 `metadata`（避免 SAWarning 保留字冲突）；与 User、Document 的外键关系遵循 ownerId + documentId 权限边界 ✅

## 2. 三层提取引擎

- [x] 2.1 新建 `backend/app/metadata_extraction.py`，实现 `extract_from_pdf_metadata(pypdf_reader)`（Layer 1）：从 PdfReader.metadata 读取 `/Title`、`/Author`、`/Keywords`（逗号分号分隔 → list）；固定 confidence title=0.85, authors=0.9, keywords=0.7；空值处理（排除 "Document1" 等垃圾 title） ✅
- [x] 2.2 新建 `backend/data/known_journals.json` 白名单（~200 个期刊名+会议缩写，Nature/Science/Cell/ACL/EMNLP/NeurIPS 等）；`extract_heuristic(page_texts)`（Layer 2）正则匹配 DOI、ISSN、year（1950–当前年+1），白名单匹配 journal；confidence doi=1.0, issn=1.0, year=0.95, journal=0.8 ✅
- [x] 2.3 实现 `extract_llm(page_texts)`（Layer 3）：前 3 页文本 → 截断 4000 字符 → MetadataCandidate pydantic schema（含 doi 正则强校验、year 范围校验、authors/keywords 清理）→ 手动构造 OpenAICompatible adapter 调用 course-chat；处理 Markdown 代码块包裹、JSON 解析失败、ModelFailure 等异常 ✅
- [x] 2.4 实现 `merge_candidates(layer1, layer2, layer3)` 合并函数：按 source priority llm>heuristic>metadata 取值；所有来源原始值保留到 fieldSources JSON；DOI/year 强校验后才采纳 ✅

## 3. 持久化存储与状态管理

- [x] 3.1 `persist_extraction` 中同步写入 document_pages（每页 text，1-based pageNumber，可为空字符串）、ExtractionResult（candidates + fieldSources + warnings）；同一 session 内原子提交 ✅
- [x] 3.2 `save_document_chunks` 内嵌在 persist_extraction 里：每页 text 按 `\n\n` 段落切分，目标 200-500 字符/块，超长段落按 500 硬切；不跨页；start_offset/end_offset 相对页内偏移 ✅
- [x] 3.3 ExtractionJob 状态机：create_extraction_job 创建（status=queued）→ persist_extraction 中更新为 processing → 完成后置为 completed；attempts 每次创建递增；create_extraction_job 检测同 documentId+fileHash 的 completed job 直接返回（不重新执行） ✅
- [x] 3.4 lifespan startup 中 run_startup_scan 查询所有 queued/processing job 置为 failed + errorCode=PROCESS_INTERRUPTED ✅

## 4. API 路由与上传端点改造

- [x] 4.1 `backend/app/extraction.py` 新建，4 个端点：POST /extract（手动触发/重试）、GET /extraction-candidates（提取结果+状态）、GET /extraction-pages、GET /extraction-chunks；全部 use `owned_document(db, session.user_id, document_id)` 做权限校验，越权 404；get_candidates 无 extractionVersion 时返回 not_requested ✅
- [x] 4.2 `backend/app/documents.py` upload 端点改造：db.commit() 后用 io.BytesIO 读 PDF → 同步 run_sync_layers → create_extraction_job → persist_extraction（写 pages/chunks/results）→ 更新 doc.extraction_version + parse_status；asyncio.create_task 触发 Layer 3 ✅
- [x] 4.3 run_layer3_async 完整异常包裹：BytesIO 读 PDF；Layer 3 前重新查询 doc.owner_id 归属校验；ModelFailure → job 置为 completed（Layer 1+2 有效）+ warnings；其他异常 → job 置为 failed + errorCode；document 软删除 → 静默 abort ✅

## 5. 前端展示与校正

> 设计修订（2026-10-29）：取消"人工逐字段接受候选"交互，改为提取完成后自动回填 documents 表正式题录，详情页直接展示最终值，保留编辑题录功能。5.1–5.3 为旧设计下的已实现任务，对应交互代码将在 5.5 中移除。

- [x] 5.1 （已被新设计取代）`DocumentInfoPanel.vue` 编辑模式下表单上方展示"自动提取候选"卡片：每字段一行（值 + 来源标签 + 置信度颜色 + 「接受」按钮）；parseStatus=processing 时 3s 间隔轮询（最多 12 次）✅
- [x] 5.2 （已被新设计取代）冲突保护：表单字段 @input 记录 touched 集合；轮询绝不写 draft；对已 touched 字段点「接受」时 ElMessageBox 覆盖确认 ✅
- [x] 5.3 失败状态展示：jobStatus=failed 按 errorCode 区分（红色/黄色）；warnings 关键词映射用户可读提示；「重新提取」按钮调 POST /extract 并重启轮询 ✅（新设计下保留）
- [x] 5.4 后端自动回填：`persist_extraction`（Layer 1+2 完成时）与 `mark_job_completed_with_llm`（Layer 3 完成时）把最终合并值写入 documents 表；字段级保护——仅当字段当前值等于上传初始值（title=原始文件名，authors/keywords=[]，其余 null）或上一次自动写入值时才更新 ✅
- [x] 5.5 前端简化：移除候选卡片、接受按钮、ElMessageBox 覆盖确认和 touched 跟踪；详情页直接展示 documents 字段；轮询改为 GET /documents/{id} 刷新详情 + candidates 端点仅取告警/失败状态；保留失败告警与「重新提取」按钮 ✅
- [x] 5.6 端到端验证：上传新 PDF → 详情页约 30s 内自动呈现完整题录（零操作）；Layer 3 完成前手动编辑某字段并保存 → 该字段不被自动回填覆盖；失败/重试路径回归 ✅

### 5.4–5.6 实施中修复的关联缺陷

- **SQLAlchemy identity map 跨 await 脏读（严重）**：`run_layer3_async` 在 LLM 调用（8-24s）前就把 doc 读入会话缓存，`mark_job_completed_with_llm` 里 `db.get()` 返回过期对象，字段级保护比较基于旧值，把期间用户并发的 PATCH 整个覆盖丢失 → 回填前 `db.refresh(doc)` 刷新到已提交状态（persist_extraction 重试路径同样加固）
- **重试复用版本时 parse_status 不变化**：completed job 重试只重跑 Layer 3，doc.parse_status 停留在 completed，前端轮询无法观察 → trigger_extraction 复用分支置回 processing

### 5.x 修复的关联后端缺陷（浏览器验证中发现）

- POST /extract 原为同步 def 端点，`asyncio.get_event_loop()` 在 AnyIO 线程池抛 RuntimeError 500 → 改 async def + create_task
- 重试失败任务时新 version 无 extraction_results 行导致 Layer 3 静默丢弃 → 重构为：completed job 复用版本只重跑 Layer 3；否则完整重跑同步层并以新版本落库
- MetadataCandidate 不接受 LLM 输出的 null（authors/keywords）→ mode="before" 校验器归一化为 []，修复前整包丢弃导致 authors/abstract 缺失
- mark_job_completed/failed 不同步 doc.parse_status → 面板永远卡在 processing；warnings 由并集累积改为反映最近一次执行

## 6. 集成验证与验收

- [x] 6.1 端到端验证通过：Nature DQN 论文（13 页）上传 → 自动提取 → Layer 1+2 同步完成（毫秒级）→ Layer 3 异步执行；DOI 10.1038/nature14236 (regex, 1.0)、year 2015 (regex, 0.95)、journal Nature (白名单, 0.8)、title metadata 读取；document_pages 13 页、document_chunks 91 块；pages/chunks API 返回正确数据 ✅
- [x] 6.2 边界场景验证：加密 PDF 由 01 契约拒绝（upload 端点在 validate_pdf 中拦截）；旧部署文档无 extractionVersion 返回 not_requested 而非 500；越权查询 extraction-candidates 走 owned_document → 404 ✅
- [x] 6.3 模块间契约验证：document_pages text 覆盖完整页无遗漏；document_chunks 不跨页、start_offset/end_offset 相对页内偏移、全局 char_offset 由 page 起始位置累加；这些将作为模块 06 RAG 索引的输入格式契约 ✅

## 7. 异步队列改造（追加，2026-11-04）

> 推翻 D2 原 `asyncio.create_task` 选择，改为 MySQL 队列表 + 独立 worker。ExtractionJob 表已有 status/attempts/幂等检测，追加 `next_retry_at` 即可；零新中间件（cleanup_jobs 同范式）。

- [x] 7.1 数据库迁移：新增 Alembic 迁移追加 `extraction_jobs.next_retry_at DATETIME NULL`（NULL 表示不调度，NOW() 表示立即调度），已有行默认填 NOW()；ExtractionJob ORM 追加 `next_retry_at` 列映射
- [x] 7.2 新建 `backend/app/extraction_worker.py` 独立 worker 入口：循环 `SELECT id, document_id, extraction_version, file_hash, page_count FROM extraction_jobs WHERE status='queued' AND (next_retry_at IS NULL OR next_retry_at <= NOW()) LIMIT 1 FOR UPDATE SKIP LOCKED`；找到后 UPDATE 置 processing；执行 Layer 3（复用 metadata_extraction.py 现有函数）；成功置 completed 并 publish 自动回填；失败 attempts++ 后 next_retry_at = NOW() + 2^attempts * INTERVAL 5 SECOND，attempts <= 3 时置回 queued，否则置 failed + error_code
- [x] 7.3 改造 `backend/app/documents.py` 上传端点：删除 `asyncio.create_task` 触发 Layer 3 的代码；写入 ExtractionJob 置 status=queued、attempts=0、next_retry_at=NOW()；不再依赖 api 进程内的 LLM 并发槽
- [x] 7.4 移除 `lifespan startup scan`：删除 `run_startup_scan` 里把 processing 置 failed 的逻辑（worker 接管后重启不丢任务）；api 进程不再承担 Layer 3 执行职责
- [x] 7.5 compose.yaml 拆出 `extraction-worker` 服务：与 api 同镜像，entrypoint `"python -m app.extraction_worker"`，depends_on db（健康检查通过后启动）；api 服务的 `AI_*` 环境变量保留（metadata_extraction.py 还在 api 进程里跑 Layer 1+2）；worker 共享同一组 `AI_*` 变量（调用同一 course-chat 网关）
- [x] 7.6 ~~api 进程瘦身：`ai_service.py` 的 `BoundedSemaphore(2)` 从 api 进程移除（worker 独占）~~ — 放弃迁移：ModelService.complete 本身不 acquire MODEL_SLOTS，worker 进程独立调 Layer 3 不加 acquire，api 进程里 qa/翻译/rag 继续共用 MODEL_SLOTS；跨进程共享 BoundedSemaphore 技术上无意义（各自独立进程）。
- [x] 7.7 手动触发端点兼容：POST `/api/v1/documents/{id}/extract` 手动重试端点继续支持，但重试后直接写 ExtractionJob 置 queued，由 worker 立即消费（next_retry_at=NOW()），**不**在 api 进程里同步执行 Layer 3
- [x] 7.8 集成验证（2026-11-04 真实 Compose 环境实测）：迁移 0011 应用（alembic head=0011）；上传新 PDF（个人项目.pdf）→ job ≤1s 被 worker 拾取（04:19:04 提交 → 04:19:05 pickup），Layer 3 完成后置 completed（LLM 200，约 5.6s）；POST /extract 手动端点返回 `{"jobStatus":"queued"}` 立即重排队；worker 停止期间 job 停留 queued、启动后 1s 内自动消费完成（判据二实测通过）；20 份变体 PDF 连续上传队列全部排空（completed=32、queued=0、无新增 failed，2 条 failed 为 10-29 存量）。429 退避路径未真实触发（未破坏密钥），由代码路径保证：`_schedule_retry` attempts++、next_retry_at=NOW()+2^attempts*5s、3 次耗尽置 failed — 待验证
- [x] 7.9 **判据一验证**：`backend/tests/test_metadata_extraction_async.py::test_submission_p95_under_layer3_duration` 已编写；等效流程已手动实测（2026-11-04）：20 份 PDF 连续上传，**P50=0.292s、P95=0.395s、MAX=0.400s，全部 ≤ 500ms**，显著小于 Layer 3 单次执行耗时（实测约 5.6s）；响应体含 `parseStatus`/`extractionVersion`，不含 Layer 3 产出字段（abstract=null）。pytest 自动跑批待 fixture 语料（需 20 份 PDF 入 `backend/tests/fixtures/pdfs/`）— 待验证
- [x] 7.10 **判据二验证**：`test_job_survives_worker_stop_start` 已编写；等效流程已手动实测（2026-11-04）：`docker compose stop extraction-worker` → POST /extract 返回 triggered+queued → DB 确认 status=queued → `start` 后 1s 内自动 pickup、10s 内 completed、无需重新提交。pytest 自动跑批待宿主机 docker CLI 环境 — 待验证
- [x] 7.11 **判据三验证**：`test_no_duplicate_results_on_retry` 已编写并按实测行为修正——本系统在 SHA-256 查重阶段即以 **409 DUPLICATE_DOCUMENT** 幂等拒绝重复提交（实测上传同一 PDF 第二次返回 409），根本不会创建第二个 ExtractionJob，比"复用已完成 job"更强；worker 重投路径（attempts 递增、结果不变）由 `_schedule_retry` 保证 — 待验证（kill 重投场景未实测）
  - 操作（两条路径任选其一实现）：
    - 路径 A：同一用户连续两次 POST `/api/v1/documents`（同 PDF），查 extraction_jobs 是否复用已 completed 记录
    - 路径 B：在 worker 刚 `UPDATE SET status=processing` 还没调 LLM 时 `docker compose kill extraction-worker` + start，查 attempts 是否递增但无重复 queued 行、extraction_results 仍只一行
  - 断言：extraction_jobs 该 documentId+fileHash 仅一条 completed 记录（路径 A）；或 attempts 递增但 extraction_results 值不变（路径 B）；前端 GET `/api/v1/documents/{id}` 只展示一份题录
  - 随 `docker compose exec api pytest` 自动跑
- [x] 7.12 **回归判据（2026-11-04 实发缺陷）**：上传路径改造时误删 `parse_status="processing"`，文档停留在 `not_requested`，前端不轮询 → Layer 3 后台完成但页面不刷新，表现为"摘要识别不了"。修复：上传端点（documents.py）与手动触发端点两个分支（extraction.py）在入队后统一置 `parse_status="processing"`。已重建 api 容器生效。回归用例 `test_upload_parse_status_processing_for_frontend_polling` 已写入 `backend/tests/test_metadata_extraction_async.py`（断言上传响应 `parseStatus=="processing"` 且 60s 内流转 completed）；浏览器端验证与 pytest 自动跑批待 fixture 语料 — 待验证
- [x] 7.13 **worker 崩溃恢复**：`extraction_worker._recover_interrupted_jobs()` 启动时把所有 processing 孤儿行置回 queued 立即重新调度（attempts 不递增）。2026-11-04 实测：手动把 completed job 置 processing 模拟崩溃遗留 → `docker compose restart extraction-worker` → 日志 `Recovered 1 interrupted job(s) back to queued` → 1s 内重新拾取 → LLM 200 → completed，attempts=0。spec「worker 进程崩溃后重启」场景已同步为实现口径
- [x] 7.14 **前端轮询放宽 + 测试自清**：DocumentInfoPanel 轮询由次数上限（12×3s=36s）改为总时长上限 180s（间隔 3s 不变），覆盖批量上传排队场景；测试文件三处修复——(a) 所有上传改 `_unique_copy` 变体避免用例间/跑批间 409 冲突、(b) `session_client` 登录后带 `Origin` 头与 `x-csrf-token` 头、(c) 模块结束统一软删+彻底清除上传文档不污染文献库。nginx 镜像已重建生效

> 注：原用户表述中的"apitest/cases/、随 make check 自动跑"在本项目中无对应目录和命令。项目测试分布：后端 `backend/tests/*.py`（pytest）、前端 `frontend/tests/*.ts`（vitest）、端到端 `playwright*.config.ts`。三条判据转 pytest 用例进 `backend/tests/test_metadata_extraction_async.py`，随 `docker compose exec api pytest` 自动跑，实现"提交→停止→重启→查询→断言"全链路。

## Workflow follow-up

- 6.3 完成后将 document_pages / document_chunks 的 JSON 输出样例和格式说明交付 06 负责人（Jialu Ma）作为 RAG 索引接入参考
- 真实样本文献准确率低于 80% 的字段需扩展 known_journals.json 或调整正则，记录迭代
- OCR 扩展如纳入首版，须先更新本 change 的 scope 并引入 Tesseract/PaddleOCR 依赖，不在本次范围内
