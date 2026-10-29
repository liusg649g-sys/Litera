## Why

上传 PDF 后手工逐字段填写题录低效且容易漏填；已有设计文档规划了 `extraction_jobs`、`extraction_results`、`document_pages`、`document_chunks` 四张表，后端 `DocumentPatch` 契约和前端 `DocumentInfoPanel` 编辑 UI 都已就位，但上传路径只做了 PDF 有效性校验，整条"提取→回填→校正→保存"链路空缺。与此同时，模块 06（AI 问答）依赖版本化页文本和可引用分块作为证据真源，没有 05 的正文提取就无法落地 RAG 索引。当前已有可用的 `course-chat` 模型网关（已通过翻译链路验证），`pypdf` 依赖已在 requirements 中，实现自动提取的基础设施已经齐备。

## What Changes

- **三层混合提取引擎**：Layer 1 读取 PDF 自带 metadata（pypdf 的 `/Title`、`/Author`、`/Keywords`），Layer 2 对前 3 页文本做正则和启发式扫描（DOI、ISSN、年份、已知期刊名白名单），Layer 3 将前 2-3 页文本交给 `course-chat` 模型做结构化 JSON 提取。任一层失败不阻塞下一层，各字段标注来源和置信度。
- **上传流程改造**：PDF 上传成功后同步执行 Layer 1+2（~50ms），立即返回部分候选让 UI 有东西可展示；异步触发 Layer 3（~2-5s），通过前端轮询补全 abstract、keywords、journal 等字段。
- **候选合并与自动回填**：在 `extraction_results` 表中持久化各层候选，每个字段带 `source`（metadata / heuristic / llm）和 `confidence`（0.0–1.0）供追溯；提取完成后自动把最终合并结果写入 documents 表正式题录，仅更新用户未手动修改的字段。
- **版本化页文本与分块**：新增 `document_pages` 表按物理 1-based 页码存储 pypdf 提取的原始文本，新增 `document_chunks` 表按每页内段落切分（200–500 字符/块），保持稳定的 `char_offset` 供后续问答的"回答→高亮原文"使用。
- **自动回填与人工校正**：提取结果自动写入正式题录后在 `DocumentInfoPanel` 详情视图直接展示（纯字段值，无来源标注）；用户通过"编辑题录"修改后经已有 PATCH `/api/v1/documents/{id}` 保存，复用 01 的 `DocumentPatch` 契约，不引入新保存入口。字段级保护：自动写入只更新仍为上传初始值或上一次自动写入值的字段，用户已修改的字段不被覆盖。
- **Open Questions 关闭**：原设计中的 Q5（字段识别策略、低置信阈值、并发参数）在本次实现中明确：DOI 用正则强校验、title 取来源中最高置信、LLM 调用限流复用 translations.py 的 `BoundedSemaphore(2)`。

## Capabilities

### New Capabilities

- `metadata-extraction`: 文献题录三层混合提取、候选持久化与来源/置信度追溯、提取结果自动回填正式题录（字段级保护）、版本化页文本与分块、提取生命周期（queued→processing→completed/failed）。

### Modified Capabilities

无；复用 01 的上传扩展点（上传成功后触发提取）和正式题录更新契约（PATCH `/api/v1/documents/{id}`），不引入新保存入口。

## Impact

- **后端**：新增 `backend/app/metadata_extraction.py`（三层提取核心）、`backend/app/extraction.py`（API 路由）；改造 `backend/app/documents.py` 的上传端点使其在成功后触发同步 Layer 1+2；新增 Alembic 迁移 0009_extraction_jobs_results_pages_chunks.py；新增 extraction 限流、并发和错误码。
- **前端**：`DocumentInfoPanel.vue` 详情视图直接展示自动回填后的题录；提取期间轮询 documents 端点刷新；保留提取失败告警与手动重试。
- **数据库**：新增 4 张表（extraction_jobs、extraction_results、document_pages、document_chunks），与 docs/design/data-model.md 规划一致。
- **依赖**：无需新增 pip 包；pypdf 已在 requirements.txt 中；course-chat 模型配置复用 .env 的 `AI_*` 变量和 `ModelService` 基础设施。
- **负责人**：Jialu Ma；模块 06（AI 问答）将消费 `document_pages` / `document_chunks` 作为输入，但不在本次实现范围内。
