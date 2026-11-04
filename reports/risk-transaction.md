# 高风险三查 · 事务 · Litera（写入同事务；停消费者 → 恢复后恰好投递一次、无孤儿任务）

**用什么手段查**：代码核对提交边界 + 消费者起停/崩溃两类实测，真实复现于 Compose 环境（提交号 000b364，2026-11-04）。

**查了什么**：
1. 提取任务记录（extraction_jobs）与提取结果记录（document_pages / document_chunks / extraction_results）是否同一事务写入
2. 消费者停止期间提交任务，恢复后是否恰好被投递执行一次
3. 消费者崩溃是否留下永远无人处理的孤儿任务

**判据**：
- `create_extraction_job`（flush）与 `persist_extraction`（flush pages/chunks/results）之后只有一次 `db.commit()`——同事务，任务存在则结果基础行必然存在
- `stop extraction-worker` → 提交 → 任务停留 queued；`start` 后自动执行至 completed，全程只完成一次，结果表仍一行
- 卡在 processing 的孤儿任务被 worker 启动回收重新入队，队列最终无残留

**结果**（实测）：

| 判据 | 实测（2026-11-04） | 判定 |
| --- | --- | --- |
| 任务+结果同事务 | documents.py L216–L221：`create_extraction_job` → `persist_extraction` → 单次 `db.commit()`；Nature DQN 13 页论文一次落齐 13 页 pages、91 块 chunks（05 验收 6.1），未见半套数据 | 绿 |
| 停消费者提交 → 恢复恰好一次 | `docker compose stop extraction-worker` → POST /extract 返回 `{jobStatus:"queued"}` → DB 确认 queued 停留 → `start` 后 **1s 内拾取、10s 内 completed**，extraction_results 仍一行，无需重新提交 | 绿 |
| 无孤儿任务 | 手动把 completed job 置 processing 模拟崩溃 → `restart` → 日志 `Recovered 1 interrupted job(s) back to queued` → 1s 内重新拾取至 completed；20 份并发上传后排空核对 queued=0 | 绿 |

**边界说明（如实）**：文献/附件行在更早的 `db.commit()`（documents.py L201）先行提交——必须先有文档行，任务才能引用；因此不变量是「任务存在 ⇒ 结果基础行存在」，反向不成立（提取层异常时文档在、任务不在，响应不含 extractionVersion，前端不进入轮询）。「恰好投递一次」是 at-least-once 投递 + 同行更新产生的实际效果，不是严格 exactly-once 语义。

**复测命令**（演示机器可原样再跑）：

```bash
# 停消费者 → 提交 → 恢复：
docker compose stop extraction-worker
# （页面上传一份新 PDF，或带会话 POST /api/v1/documents）
docker compose exec db mysql -ulitera -p"$MYSQL_PASSWORD" litera \
  -e "SELECT status FROM extraction_jobs ORDER BY created_at DESC LIMIT 1;"
# 期望输出：queued（任务不丢、未执行）
docker compose start extraction-worker
docker compose logs extraction-worker --tail 5
# 期望日志：Picked up job ... → HTTP 200 → Auto-backfilled ...（仅一条拾取记录）
docker compose exec db mysql -ulitera -p"$MYSQL_PASSWORD" litera \
  -e "SELECT status, attempts FROM extraction_jobs ORDER BY created_at DESC LIMIT 1;"
# 期望输出：completed，且同版本 extraction_results 仅一行

# 自动化版本（判据二，fixture 语料齐备后）：
pytest -v backend/tests/test_metadata_extraction_async.py::test_job_survives_worker_stop_start
```

要点：本条是最终报告「高风险三查 · 事务」的直接来源——写入侧靠单事务 commit，消费侧靠 queued 停留 + 启动回收，两头都附了当场可复跑的命令与期望值。
