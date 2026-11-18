# 评审记录初稿 · review-04 · 幂等与并发自审

**状态**：初稿，待人工复核并定稿。

## 用什么手段查

- AI 自审 + 脚本：`apitest/cases/extr-duplicate.ps1`、`docs-upload-duplicate-409.ps1`、`extr-stale-recovery.ps1`、`extr-cutover-recovery.ps1`。
- 记录：`reports/risk-concurrency.md`，性能阈值见 `reports/bench.md`。

## 查了什么

- 同一份 PDF 连续投递两次，是否只产生一个文档和一个题录任务。
- worker 重复投递、进程中断、旧代码崩溃后，是否会在同一 `documentId + fileHash` 上重复建任务。
- 迁移 0012 新增唯一键和计数列后，重复提交是否返回 409，原任务是否保留。
- 并发提交时队列是否堆积，P95/MAX 是否超阈值。

## 判据

- `extraction_jobs` 对同一 `documentId + fileHash` 最多一行；`extraction_results` 对同一版本最多一行。
- 重复提交必须返回 `409 DUPLICATE_DOCUMENT`，不得新建第二个任务。
- 崩溃恢复只更新原任务并递增 `attempts`，不插入新行。
- 20 次连续上传 P95 ≤ 0.5s、MAX ≤ 2.0s，队列在 300s 内排空。

## 结果

- 重复投递两次只产生一个任务，第二次返回 `409 DUPLICATE_DOCUMENT`。
- 中断/旧代码崩溃恢复走同一行更新，`attempts` 递增，未产生重复结果。
- 迁移 0012 的唯一键生效，重复插入被数据库拒绝。
- 最近一次 `make check`：20 次上传 P95=0.200s、MAX=0.203s，队列排空。

## 未覆盖与人工复核

- “同一份提交”目前按 `documentId + fileHash` 判定，跨用户同文件是否应共享仍需产品确认。
- k6 的 20 VU/60s 压测尚未落盘，当前数据来自 PowerShell 20 次上传门禁。
