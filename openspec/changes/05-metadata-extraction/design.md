# Design

## Context

动机见 proposal.md。Jialu Ma负责，待实现。01 首版 parseStatus=not_requested、上传事件只是扩展点；当前没有解析或作业实现。05 为 06 提供证据真源。

## Goals / Non-Goals

**Goals:** 输出版本一致的页文本/分块与题录候选，容许缺字段并保护人工信息。

**Non-Goals:** 不绕过 01 文件服务，不静默覆盖人工题录，不在本次实现 PyMuPDF/OCR。

## Decisions

1. PyMuPDF 适配器从私有文件服务获取输入；后续采用持久 extraction_jobs 与可恢复工作进程。相比请求内 BackgroundTasks，可观察重启、失败和幂等；具体服务拆分见架构文档。
2. DocumentUploadedV1 在文件/DB 成功后启用可靠触发，事件/文件版本幂等；工作前与发布前复验文献可用。失败不影响上传成功记录。
3. 元数据作为独立候选结果，人工选择后使用 01 version PATCH。相比直接自动写 documents，避免与手工校正竞争。
4. 页面采用物理 1-based；分块不跨页，Unicode code point 半开偏移。版本完成事务原子发布 pages/chunks 和 active extractionVersion，向 06 通知 ExtractionReadyV1。格式见 [API](../../../docs/design/api-contracts.md)。
5. 无文本扫描 PDF 标记正文不可用，无 OCR 首版不伪造文本；字段可未知，有警告不等于上传失败。

## Risks / Trade-offs

- [布局复杂导致候选不准] → 来源/警告/人工校正，不声称字段全准。
- [进程中断或重复任务] → 持久状态、幂等和受控重试，测试中断恢复。
- [重解析使引用漂移] → 显式版本，06 索引与引用固定版本，不复用新文本替代旧来源。

## Migration Plan

后续新增 extraction_jobs/results/pages/chunks 表与工作进程 → 手动触发 API → 题录候选/校正 → 接入上传事件和 06。回退禁用触发，保留现有文献/人工题录与最后有效提取版本。不存在本批迁移或解析调用。

## Open Questions

Q5 的字段识别策略、低置信阈值、资源/并发参数待样本评估；OCR 如纳入首版则须先修改范围和规格，不把待确认项视为已承诺功能。
