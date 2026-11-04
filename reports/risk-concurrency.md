# 高风险三查 · 并发 · Litera（判据三：重复提交 / 重复投递只出一份结果）

**用什么手段查**：幂等接口用例（同一 PDF 连续两次提交）+ worker 重复投递路径实测，真实复现于 Compose 环境（提交号 000b364，2026-11-04）。

**查了什么**：题录提取改为异步任务与消息队列后，两条重复路径是否都只产出一份结果——
1. 入口侧：同一用户重复提交同一 PDF（并发生产消息）
2. 消费侧：worker 重试、崩溃恢复导致的同一任务被重复投递/重复执行

**判据**：
- `extraction_jobs` 中同一 documentId + fileHash 仅有一条生效记录
- `extraction_results` 中同一 extractionVersion 仅一行；重复执行只更新同一行，attempts 可递增但题录值不变
- 前端 GET /api/v1/documents/{id} 只展示一份题录

**结果**（实测）：
- **重复提交**：2026-11-04 实测第二次 POST 同一 PDF 返回 **409 DUPLICATE_DOCUMENT**（`error.code=DUPLICATE_DOCUMENT`）——在 SHA-256 查重阶段即幂等拒绝，根本不创建第二个 ExtractionJob，比「复用已完成 job」更强。同 hash 并发由上传端点 `db.flush()` + 唯一约束序列化（documents.py L197-198 注释处）
- **重复投递**：worker 对同一 job 的重试/恢复重跑只 UPDATE 同一 job 行与同一 results 行；崩溃恢复实测（2026-11-04）：processing 孤儿 job 被回收重排队后再次执行至 completed，attempts=0，无第二行结果
- 20 份变体并发上传队列排空后核对：completed=32、queued=0，无重复任务行

**复测命令**（演示机器可原样再跑）：

```bash
# 自动化版本（fixture 语料齐备后）：
pytest -v backend/tests/test_metadata_extraction_async.py::test_no_duplicate_results_on_retry
# 断言：第二次提交返回 409 且 error.code == "DUPLICATE_DOCUMENT"

# 手动版（口令由执行者填入；先登录取 jar 与 csrfToken）：
curl -s -c jar -H "Origin: http://localhost:8085" -H "Content-Type: application/json" \
  -d '{"email":"<账号>","password":"<口令>"}' http://localhost:8085/api/v1/auth/login
TOKEN=<登录响应中的 csrfToken>
curl -s -o /dev/null -w "%{http_code}\n" -b jar -H "Origin: http://localhost:8085" -H "x-csrf-token: $TOKEN" \
  -F "file=@same.pdf;type=application/pdf" http://localhost:8085/api/v1/documents   # 期望 201
curl -s -b jar -H "Origin: http://localhost:8085" -H "x-csrf-token: $TOKEN" \
  -F "file=@same.pdf;type=application/pdf" http://localhost:8085/api/v1/documents   # 期望 409 + DUPLICATE_DOCUMENT

# 任务表核对（期望同一文档只有一条 job）：
docker compose exec db mysql -ulitera -p"$MYSQL_PASSWORD" litera \
  -e "SELECT document_id, file_hash, COUNT(*) FROM extraction_jobs GROUP BY document_id, file_hash HAVING COUNT(*)>1;"
# 期望输出：空集
```

要点：本条是最终报告「高风险三查 · 并发」的直接来源——幂等性由入口查重（409）+ 唯一约束序列化（生产侧）与同行更新（消费侧）共同保证，两条路径都有可复跑的命令。
