## Purpose

将用户私有 PDF 转化为可自动回填的题录结果和带物理页码的正文证据。系统在上传后自动执行三层混合提取（PDF 自带 metadata、正则启发式、course-chat LLM），每个字段记录来源和置信度供追溯，提取完成后将最终合并结果自动写入正式题录并在详情页直接展示，仅跳过用户已手动修改的字段；同时持久化版本化的页文本和分块供后续问答模块使用。

## ADDED Requirements

### Requirement: 三层混合提取与候选合并
系统 SHALL 在 PDF 上传成功后按 Layer 1（PDF metadata）→ Layer 2（正则启发式）→ Layer 3（course-chat LLM）顺序执行提取。每层的产出作为独立候选保存，各字段在合并时按 `llm > heuristic > metadata` 优先级取值，同时保留所有来源的原始值供人工查阅。任一层失败不得阻塞其他层或标记整个提取失败。

#### Scenario: 三层全部成功
- **WHEN** 上传的 PDF 包含可读取 metadata、可提取文字且 course-chat 可用
- **THEN** extraction_results 中 7 个题录字段均有值，每个字段标注 source 和 confidence；title 优先取 LLM 结果，doi 优先取正则结果，未出现在任何层的字段为 null

#### Scenario: LLM 层失败但前两层成功
- **WHEN** Layer 1+2 正常完成但 course-chat 超时或返回不可解析响应
- **THEN** 已从 metadata/heuristic 获得的字段（如 doi、year）保持有效并自动回填；abstract、keywords、journal 标记为 null；extraction_jobs 状态仍为 completed，同时记录 warnings；前端详情页展示已回填字段和提取警告，用户仍可校正

#### Scenario: 三层均失败
- **WHEN** PDF 无法读取 metadata、无可提取文本且 LLM 不可达
- **THEN** extraction_jobs 状态为 failed，errorCode 为 EXTRACTION_NO_TEXT；extraction_results 仅含 warnings；document_pages 为空数组；上传本身成功，文档仍可查看

### Requirement: 提取任务生命周期与状态
系统 SHALL 在 PDF 上传成功后自动创建 extraction_job，状态流转为 queued → processing → completed/failed。相同 documentId + fileHash 的重复请求不得创建重复活动作业。用户可手动触发重试，重试创建新版本 extractionVersion 而非覆盖旧版本。

#### Scenario: 上传触发自动提取
- **WHEN** 用户成功上传本人 PDF 文档
- **THEN** 系统立即可查询到 extraction_job，初始状态 queued，在 500ms 内进入 processing，完成后自动更新为 completed 或 failed

#### Scenario: 重复上传同一文件
- **WHEN** 同一用户重复上传 SHA-256 相同的 PDF
- **THEN** documents 表创建新记录（遵循 01 契约），但 extraction_job 复用已完成的版本（不重新执行 Layer 3 LLM），在 extraction_results 中记录引用而非重新提取

#### Scenario: 手动重试失败的提取
- **WHEN** 用户对 failed 状态的 extraction_job 触发重试
- **THEN** 创建新版本 extractionVersion，重新执行三层提取；旧版本的 extraction_results、document_pages、document_chunks 保留直到新版本完成，前端默认展示新版本候选

### Requirement: 题录字段候选与来源标注
系统 SHALL 为 title、authors、abstract、keywords、year、journal、doi 七个题录字段输出候选值，每个字段必须携带 source（metadata / heuristic / llm）和 confidence（0.0–1.0）。未知字段为 null（对象字段）或空数组（数组字段），不得用猜测值补齐。

#### Scenario: 所有字段均有候选
- **WHEN** 三层提取均返回有效值
- **THEN** 每个字段的值、source、confidence 齐备；title 默认取 LLM 结果（confidence 0.8+），doi 默认取正则结果（confidence 1.0），authors 默认取 metadata（confidence 0.9）

#### Scenario: 部分字段空缺
- **WHEN** PDF 无 DOI 和 keywords
- **THEN** doi=null、keywords=[]，source 和 confidence 为 null；不生成"0000-0000"之类的占位值

#### Scenario: DOI 正则与 LLM 结果冲突
- **WHEN** 正则从 PDF 首页提取到 `10.1038/nature12345` 而 LLM 返回不同 DOI
- **THEN** 合并时取正则结果（confidence 1.0），同时在 extraction_results.fieldSources 中保留 LLM 返回值供追溯；详情页只展示最终合并值

### Requirement: 版本化页文本与分块契约
系统 SHALL 将每页可提取文本按物理 1-based 页码存入 document_pages，再按每页内段落切分为 document_chunks。分块保持 200–500 字符目标长度、不跨页、携带稳定的 char_offset 和 pageIndex。document_pages 与 document_chunks 必须在同一个 extractionVersion 下原子发布；版本标记为 active 前，下游 06 不得读取半成品。

#### Scenario: 下游读取完成版本
- **WHEN** 模块 06 对已发布 extractionVersion 的文档请求页文本和分块
- **THEN** 每个 chunk 可映射到同 document_pages 的同 pageNumber，pageNumber 与 PDF 物理页码一致，char_offset 在拼接全文的全局偏移范围内

#### Scenario: 处理尚未完成
- **WHEN** 下游请求状态为 processing 的 extractionVersion
- **THEN** 返回 404，不暴露任何 page 或 chunk 行

#### Scenario: 页面无可提取文字
- **WHEN** PDF 第 1 页为扫描件或纯图片，无 pypdf 可读取文本
- **THEN** document_pages 中该页的 text 为空字符串，document_chunks 中该页无记录；extraction_results.warnings 记录页码和原因

### Requirement: 异步 Layer 3 触发与前端刷新
系统 SHALL 在同步完成 Layer 1+2 后立即返回上传成功并回填已得字段（title、doi、year 等），同时通过后台任务异步执行 Layer 3 LLM 提取。前端在上传成功后自动轮询文档详情端点（间隔 2-3 秒，最多 12 次）；Layer 3 完成后 abstract、keywords、journal 等字段自动回填并在详情页补全显示。

#### Scenario: Layer 3 在超时前完成
- **WHEN** course-chat 在 2–5 秒内返回有效 JSON
- **THEN** 详情页在下次轮询时展示补全的 abstract、keywords；已由用户编辑过的字段保持原值不被覆盖

#### Scenario: Layer 3 超过 30 秒或返回无效格式
- **WHEN** course-chat 超时、返回非 JSON 或字段校验失败
- **THEN** 后端将 Layer 3 结果标记为 failed，warnings 中记录原因；详情页展示 Layer 1+2 已回填的字段，不影响用户校正和保存

#### Scenario: Layer 3 完成时用户已编辑部分字段
- **WHEN** Layer 3 完成时用户已在前端手动修改 title 字段并保存
- **THEN** Layer 3 自动回填跳过 title，仅更新其余未触碰字段；用户可继续编辑后手动保存

### Requirement: 自动回填与正式题录保护
系统 SHALL 在提取完成后自动将最终合并结果写入 documents 表正式题录，使详情页无需人工操作即可展示提取结果。自动写入 MUST 仅更新仍为上传初始值（title 为原始文件名、其余字段为空或 null）或上一次自动写入值的字段；用户已手动修改的字段不得被覆盖。用户校正**必须**通过已有 PATCH `/api/v1/documents/{id}` 保存，复用 01 的 `DocumentPatch` 契约。

#### Scenario: 提取完成后详情直接展示
- **WHEN** 提取完成且用户未做任何编辑
- **THEN** 详情页直接显示提取的 title、authors、abstract、keywords、year、journal、doi 字段值，无需任何"接受"操作

#### Scenario: 用户在自动回填基础上编辑后保存
- **WHEN** 用户修改了自动回填的 authors 和 abstract 后点保存
- **THEN** 保存的是用户编辑后的值，而非原始提取值

#### Scenario: 自动回填晚于手工编辑
- **WHEN** 用户已手动填写并保存部分字段，自动提取（或 Layer 3）才完成
- **THEN** 自动回填跳过用户已修改的字段，仅补全其余未触碰字段；PATCH 携带的 version 与 documents.version 不一致时返回 409，防止静默覆盖

### Requirement: 提取失败与不可解析反馈
系统 SHALL 对加密 PDF、损坏 PDF、无可提取文本、course-chat 超时/429/无效响应提供明确的错误码和用户可读警告。失败不得回滚已成功上传的文件或伪造供 06 使用的正文。

#### Scenario: 扫描 PDF 无文字
- **WHEN** PDF 不含可提取文本且未启用 OCR
- **THEN** 前端在 DocumentInfoPanel 顶部显示警告"未检测到可识别的正文文本"；extraction_results 所有 metadata 字段为 null，document_pages 的 text 字段均为空字符串；问答模块不得将此文档标记为可检索正文

#### Scenario: course-chat 返回 429 限流
- **WHEN** course-chat 返回 429 或连接超时
- **THEN** 后端记录 warnings="MODEL_QUOTA_LIMITED"；extraction_jobs 状态为 completed（Layer 1+2 成功），但 Layer 3 相关字段保持 null；前端提示"AI 模型暂时不可用，部分字段未提取"

### Requirement: 提取权限与资源隔离
系统 SHALL 在提交、查询和执行提取任务前验证 documentId 归属和可用状态。越权访问返回 404（不泄露他人资源存在性）；软删除文献阻断新结果发布，永久删除清理所有派生数据（extraction_jobs、extraction_results、document_pages、document_chunks）。

#### Scenario: 越权查询他人 extraction_job
- **WHEN** 用户尝试 GET 非本人 documentId 的 extraction candidates 或 jobs
- **THEN** 返回 404，不区分"文献不存在"和"无权访问"

#### Scenario: 提取期间文献被软删除
- **WHEN** extraction_job 仍在 processing 中用户删除了该文献
- **THEN** processing 任务检测到 documents.deletedAt 非空后停止，不得发布 extraction_results、document_pages 或 document_chunks；已创建的 job 标记为 failed 并记录 warning 说明原因
