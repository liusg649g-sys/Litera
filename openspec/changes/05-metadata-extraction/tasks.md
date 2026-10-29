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

## Workflow follow-up

- 6.3 完成后将 document_pages / document_chunks 的 JSON 输出样例和格式说明交付 06 负责人（Jialu Ma）作为 RAG 索引接入参考
- 真实样本文献准确率低于 80% 的字段需扩展 known_journals.json 或调整正则，记录迭代
- OCR 扩展如纳入首版，须先更新本 change 的 scope 并引入 Tesseract/PaddleOCR 依赖，不在本次范围内
