# 性能基线（`make check`）

本文件记录性能门禁的固定环境、阈值与最近一次实测结果，供评审复查。
生产环境或不同机器上的数值不可直接与本表比较。

## 环境

| 项 | 值 |
| --- | --- |
| 日期 | 2026-11-18 |
| 入口 | `http://localhost:8085/api/v1`（nginx → api） |
| 数据库 | Docker Compose 内 MySQL 8.4 |
| 存储 | 本机 Docker volume |
| 模型调用 | 不参与性能门禁；上传接口只测异步提交与入队 |
| 隔离用例库 | 临时 SQLite（每次门禁重建） |

## k6 目标参数

| 参数 | 值 |
| --- | --- |
| vus | 20 |
| duration | 60s |
| 场景 | 登录后循环提交 PDF，统计上传提交 P95/MAX 并等待队列排空 |

当前仓库的可复跑压测入口是 `apitest/cases/extr-p95-concurrency.ps1`（20 次上传）；k6 脚本尚未落盘，本机也未安装 k6。因此下表中的 P95/MAX 来自 PowerShell 门禁，不是 k6 结果。

## 返工前后 P95

| 阶段 | P95 | MAX | 说明 |
| --- | --- | --- | --- |
| 返工前 | 未留存 | 未留存 | 没有可检索的原始输出，不能用推测值补齐 |
| 返工后 | 0.200s | 0.203s | 2026-11-18 `make check`，20 次上传 |

## 阈值与结果

| 门禁 | 阈值 | 实测 | 证据 |
| --- | --- | --- | --- |
| 20 次上传提交 P95 | ≤ 0.5s | 0.200s | [extr-p95-concurrency.ps1](../apitest/cases/extr-p95-concurrency.ps1) |
| 20 次上传提交 MAX | ≤ 2.0s | 0.203s | 同上 |
| 队列排空 | 300s 内 0 条未完成 | 0 | 同上 |
| 50 行文献列表 SELECT 数 | ≤ 12 | 4 | [query-performance.json](query-performance.json) |
| 50 行笔记列表 SELECT 数 | ≤ 12 | 4 | 同上 |
| 单条 SQL 最大耗时（SQLite 隔离库） | ≤ 100ms | 1.47ms（文献）/ 0.939ms（笔记） | 同上 |

最近一次完整门禁在本地输出 `reports/check-all-*.log`（`*.log` 被 gitignore，不入库）；可复跑的入口是 `make check`。

## 说明

- P50/P95/MAX 只覆盖上传提交阶段，不包含 LLM 提取耗时；提取完成由队列排空条件单独验证。
- N+1 门禁使用 50 行固定数据，任一列表出现按行查询会超过 SELECT 上限。
- 本轮门禁发现并修复了文献列表、笔记列表的逐行查询；复合索引由迁移 `0013_index_alignment` 对齐。
- 更换机器、数据库或镜像后需重跑 `make check` 并更新本表。
