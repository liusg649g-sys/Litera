# 高风险三查 · 权限 · Litera

**用什么手段查**：接口用例——用户 A 的会话直接调用户 B 的资源 id（跨用户访问），以及越权查询提取结果。

**查了什么**：他人文献详情是否可读；他人提取结果（extraction-candidates）是否可读；无会话时接口是否一律 401。

**判据**：跨用户访问一律 404（先按 owner_id 过滤再取数），与访问不存在 ID 的返回完全相同（排除随机 requestId 后）；不带会话一律 401。

**结果**：
- 未登录 401：2026-11-04 于 000b364 实测两遍（含 review-01 独立复现），5 个受保护接口全部 401 —— 绿
- 跨用户 404：05 验收 6.2（2026-10-29）实测越权查询 extraction-candidates 经 owned_document 返回 404；实现上 documents / extraction / qa / annotations 各端点统一走 `owned_document(db, session.user_id, id)` —— 绿

**复测命令**（演示机器可原样再跑；`<口令A>` `<口令B>` 由执行者填入）：

```bash
# 用户 A 登录，取会话 Cookie 与 CSRF
curl -s -c jarA -H "Origin: http://localhost:8085" -H "Content-Type: application/json" \
  -d '{"email":"user-a@example.com","password":"<口令A>"}' \
  http://localhost:8085/api/v1/auth/login

# 用 A 的会话访问 B 的文献（id 来自 B 的账号），期望：404
curl -s -o /dev/null -w "%{http_code}\n" -b jarA \
  http://localhost:8085/api/v1/documents/<B的文档id>

# 越权查 B 的提取结果，期望：404
curl -s -o /dev/null -w "%{http_code}\n" -b jarA \
  http://localhost:8085/api/v1/documents/<B的文档id>/extraction-candidates

# 访问不存在的 id，期望：与上面完全相同的 404 语义
curl -s -b jarA http://localhost:8085/api/v1/documents/00000000-0000-0000-0000-000000000000

# 不带会话，期望：401
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8085/api/v1/documents/<B的文档id>
```

要点：404 与 401 的值在哪台机器跑都相同；「B 的文档 id」每次演示前从 B 账号的文献库取一个真实值填入即可。
