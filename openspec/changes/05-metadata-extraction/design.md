## Context

见 proposal.md。模块 01 已实现 `POST /api/v1/documents` 上传端点（pypdf 校验 PDF 有效性后入卷、写 documents 表）、`PATCH /api/v1/documents/{id}` 正式题录更新端点（`DocumentPatch` 包含 title/authors/abstract/keywords/year/journal/doi 字段及 version 乐观锁）；前端 `DocumentInfoPanel.vue` 已实现题录编辑和保存。`docs/design/data-model.md` 已规划 extraction_jobs、extraction_results、document_pages、document_chunks 四张表。本次将"上传→提取→自动回填→校正"链路补全为可运行的自动流程。

已有可复用基础设施：
- **pypdf** 已在 `requirements.txt` 中（用于 Layer 1 metadata 读取和 Layer 2/3 页文本提取）
- **course-chat 模型网关**（已通过模块 03 翻译链路验证，配置在 `.env` 的 `AI_*` 变量中）
- **并发限流** `BoundedSemaphore(2)` 和 `ModelService.complete()` 可从 `backend/app/ai_service.py` 复用，不重复造轮子
- **错误映射** `ModelFailure` 和统一 error 包络已在 ai_service.py / translations.py 中实现

## Goals / Non-Goals

**Goals:**
- 上传后 Layer 1+2 同步完成 ~50ms，Layer 3 异步完成 ~2-5s
- 每个字段的候选可追溯到具体来源层和置信度
- document_pages 和 document_chunks 满足模块 06 消费的格式契约
- 提取结果自动回填正式题录，仅覆盖未触碰字段；人工校正后显式触发保存

**Non-Goals:**
- 不引入 OCR 处理扫描 PDF（无文字层的 PDF 标记警告，不伪造文本）
- 不实现后台 worker 进程或事件总线（Layer 3 用 `asyncio.create_task` fire-and-forget）
- 不实现 RAG embedding 或问答本身（06 的领域）
- 不替换 GROBID 等外部专业工具（依赖 course-chat，已在上游验证可用）
- 不修改 01 的上传契约或 02 的阅读器渲染逻辑

## Decisions

### D1: 三层混合提取而非单一 LLM 或单一 GROBID

**选择**：Layer 1（pypdf metadata）+ Layer 2（正则启发式）+ Layer 3（course-chat）混合。

**原因**：
- 成本可控：前两层零成本本地执行；LLM 仅在前两层空缺字段时补全（~2000-4000 token/次，course-chat 额度充足）
- 速度分层：Layer 1+2 毫秒级返回让 UI 立即可见；Layer 3 异步不阻塞上传响应
- 准确性互补：DOI 正则（Layer 2, confidence 1.0）比 LLM 准（LLM 可能幻觉编造）；PDF metadata 的 title/author（Layer 1）通常比 LLM 准；abstract/keywords/journal 只有 LLM 能可靠给出
- 降级有保障：任一层失败不阻塞；LLM 超时时仍有 Layer 1+2 候选可用

**替代方案**：
- 纯 GROBID：需要额外部署 GROBID 服务（~1GB Docker 镜像 + Java 运行时），本次 11 合不上
- 纯 LLM：成本略高 + 幻觉风险 + 速度不能保证 < 3 秒

### D2: 同步 Layer 1+2 + 异步 Layer 3 触发

**选择**：上传端点在同一个 HTTP 请求内同步执行 Layer 1+2（不阻塞响应时长），然后用 `asyncio.create_task()` fire-and-forget 提交 Layer 3。前端通过轮询 `GET /api/v1/documents/{id}` 刷新详情页展示；`extraction-candidates` 端点仅用于失败状态与告警查询。

**原因**：
- 不阻塞上传响应：上传成功立即返回 201 + `parseStatus=processing` + 部分候选
- 不引入 Celery/RQ/独立 worker 进程（增加运维复杂度）
- `asyncio.create_task` 在 FastAPI lifespan 内生命周期管理足够，进程重启时未完成的 job 自动标记 failed 等待重试
- 前端轮询实现简单（2s 间隔 × 最多 10 次 = 20s 内完成或放弃），不需要 SSE/WebSocket 基础设施

**替代方案**：
- 全部同步等待：用户上传 PDF 后被迫等待 2-5s LLM 响应，体验差
- 独立 worker 进程：额外 Docker 服务 + 进程间通信 + 进程重启恢复，对本次 MVP 过重

### D3: 提取结果自动回填正式题录，候选表保留追溯

**选择**：extraction_results 表存候选（含 source/confidence/fieldSources）供追溯；Layer 1+2 完成和 Layer 3 完成两个时点，把最终合并结果自动写入 documents 表正式题录。字段级保护：仅当字段当前值等于上传初始值（title=原始文件名、其余为空）或等于上一次自动写入值时才更新。

**原因**：
- 自动提取的大多数字段无需人工干预，逐字段"接受"是多余点击；直接回填让详情页上传后即可用
- 字段级比较保护保证用户手动修改不被覆盖，配合 01 的 version 乐观锁防止并发写冲突
- extraction_results 与 documents 分离仍保留来源追溯能力（哪层提取的、置信度多少），便于评估提取质量和迭代白名单/正则

**替代方案**：
- 候选卡片 + 人工逐字段接受（首版已实现，本轮被否决）：多一次点击且大多数字段无需干预
- 候选与正式题录完全分离、仅前端展示层合并：列表页/搜索仍看到旧值，两处真源不一致
- 自动结果无条件覆盖 documents：会破坏用户手动修改，不可接受

### D4: document_chunks 简单按段落切分，不做语义分块

**选择**：每页文本按 `\n\n` 段落切分，目标 200–500 字符/块，不跨页，保持 char_offset 全局连续。

**原因**：
- 本次 MVP 的分块目标是为模块 06 提供可用的检索单元，不是追求最优质的语义边界
- 不跨页保证"chunk → pageNumber → PDF 物理页"的稳定映射，问答高亮时不会错位
- char_offset 从 page 起始累加，全局连续，便于"回答→原文"定位

**替代方案**：
- 语义分块（句子/段落边界 + token 数）：实现复杂度高且需要 06 的 embedding 逻辑配合才能评估效果，本次先行

### D5: 复用 translations.py 的 LLM 限流与错误处理

**选择**：extraction 的 LLM 调用复用 `ai_service.py` 的 `ModelService.complete()`、`BoundedSemaphore(2)`、`ModelFailure` 错误映射，不另起一套。

**原因**：
- 翻译链路已在生产环境验证，course-chat 网关、超时设置（连接 5s / HTTP 30s）、错误码映射（MODEL_AUTH / MODEL_QUOTA / MODEL_TIMEOUT）全部可用
- 复用减少维护成本；两个功能共享同一套额度和并发限制符合实际

**风险**：翻译和提取同时进行时共享并发槽（最多 2 个 LLM 调用），可能导致短暂队列等待。→ 已有 `TRANSLATION_BUSY` 语义在 translations.py 中，extraction 同样返回可重试状态。

### D6: known_journals.json 白名单匹配而非自由文本匹配

**选择**：维护一个 `backend/data/known_journals.json`，包含 ~200 个常见期刊名和会议名缩写。Layer 2 仅在白名单中匹配成功时才填 journal 字段，不猜测。

**原因**：
- 启发式从自由文本提取期刊名容易误判（把机构名、出版社名当成期刊）
- 白名单保证只填有把握的值，宁缺毋滥
- 白名单可迭代扩充（用户反馈 + 实际文献样本）

**替代方案**：
- 正则匹配 "Journal of XXX" / "Proceedings of XXX" 模式：误判率高
- 完全依赖 LLM：能补全但 confidence 较低，需人工确认

## Risks / Trade-offs

| 风险 | 缓解 |
|---|---|
| 自动回填覆盖用户正在编辑的字段 | 字段级比较保护（仅更新仍为初始值/上次自动值的字段）+ PATCH version 乐观锁 |
| course-chat 限额耗尽或响应慢导致 Layer 3 失败 | Layer 1+2 作为保底，失败时 warnings 明确告知用户；前端提示可稍后重试 |
| `asyncio.create_task` 在进程重启时丢失未完成的 Layer 3 | 进程启动时扫描 processing 状态的 extraction_job，置为 failed 等待用户重试；不自动重跑避免重复请求 |
| 大 PDF（> 200 页）text extraction 较慢 | Layer 1+2 只看前 3 页（Layer 3 也只取前 3 页文本），document_pages 全量逐页提取但独立执行；如遇 > 50MB PDF 由 01 上传限制提前拦截 |
| LLM 返回幻觉字段（如编造 DOI） | DOI、ISSN、year 都有正则强校验，不合规直接丢弃；title/journal 等文本字段标注 confidence=0.6 提示人工确认 |
| module 06 对 document_chunks 格式有额外要求 | design 中 char_offset + pageNumber + chunkIndex 已覆盖"问答→高亮原文"所需最小字段；后续根据 06 需求增量调整 |
| Docker 容器内 LLM 调用需要能访问 course-chat 网关 | 验证 course-chat 网关（https://ai-gateway.devops.hello1023.com/v1）在 Docker 容器内可达，已通过翻译链路验证 |

## Migration Plan

### 实施步骤

1. **数据库迁移**：新增 Alembic 迁移 `0009_extraction_jobs_results_pages_chunks.py`，创建 4 张表，与 data-model.md 规划一致。执行前备份现有数据库卷。
2. **后端模块**：实现 `metadata_extraction.py`（三层提取引擎 + 候选合并逻辑）、`extraction.py`（API 路由：手动触发、状态查询、候选查询、重试）。
3. **上传端点改造**：`documents.py` 的 POST `/documents` 在成功后调用 `extract_service.trigger_sync_layers(doc_id, file_hash, page_count)` 同步 Layer 1+2，然后 `asyncio.create_task(trigger_layer3(...))`。
4. **前端改造**：`DocumentInfoPanel.vue` 详情视图直接展示自动回填结果，上传后轮询 documents 端点刷新；保留提取失败告警与手动重试。
5. **集成测试**：上传 3-5 份真实 PDF，验证三层输出合并、候选展示、校正保存、失败重试全链路。

### 回滚策略

- 禁用触发：在 `.env` 中增加 `EXTRACTION_ENABLED=false` 开关，关闭自动触发；手动端点仍可用。
- 保留已生成的数据：extraction_* 表不删除，已保存的正式题录不受影响。
- 恢复数据卷：如迁移导致数据库损坏，恢复 MySQL 命名卷备份，回到迁移前状态。

### 部署注意

- 新增的 4 张表需要 Alembic 迁移，Compose 启动时自动执行 `alembic upgrade head`（与现有流程一致）
- Layer 3 异步任务依赖 API 容器存活，容器重启时 processing 中的 job 会在启动后被扫描置为 failed
- Docker 容器内需要能访问 `https://ai-gateway.devops.hello1023.com/v1`（已验证可达）

## Open Questions

当前无 open questions。所有设计决策（三层架构、触发方式、存储解耦、分块策略、限流复用、期刊白名单）在本轮讨论中已明确，不影响 specs、design 和 tasks 的最终形态。
