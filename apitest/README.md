# apitest/ -- API-level acceptance suite (black-box against the real Compose stack)

每条用例是一个可直接执行的 PowerShell 脚本，内部为三段式（前置条件 → 操作 → 断言），
跑完打印 `CASE <name> GREEN/RED/SKIP`。`make check` 串起全部用例并汇总。

## 前置条件

1. Compose 全栈已启动且健康：`docker compose ps`（db / api / extraction-worker / nginx）
2. 凭据（仅涉及登录态的用例需要）：
   - 方式一（推荐，不进仓库）：复制 `config.example.ps1` 为 `config.local.ps1` 填账号 A（越权用例再填账号 B）
   - 方式二：环境变量 `APITEST_EMAIL` / `APITEST_PASSWORD`（可选 `APITEST_EMAIL_B` / `APITEST_PASSWORD_B`）
3. 可选：`APITEST_BASE` 覆盖目标地址，默认 `http://localhost:8085/api/v1`

## 跑法

```powershell
make check                 # 全部用例
make check FILTER=docs-*   # 只跑某组
```

等价于 `powershell -NoProfile -ExecutionPolicy Bypass -File apitest/run_checks.ps1 [-Filter <glob>]`。
汇总行 `GREEN n / RED n / SKIP n`；有 RED 退出码为 1。每次跑批输出落盘 `apitest/reports/check-<时间戳>.log`。

## 目录

- `cases/` 用例本体：auth-*（认证）、docs-*（文献）、anno-*（批注）、extr-*（提取/异步队列）、trans-*（翻译与模型）、notes-*（笔记）、qa-*（问答）、x-*（横切矩阵）
- `lib/common.ps1` 登录（含 10 分钟会话缓存避开 20 次/分钟限流）、HTTP 封装、断言、清理
- `lib/fixtures.ps1` fixture 路径、SHA-256 变体生成、队列排空等待
- `fixtures/` 语料：normal.pdf（含 DOI 10.5555/apitest.2026.001 与 zebra-telegraph 特征句）、injection.pdf（SEC-08 注入语料）

## 约定

- 上传的文档用例结束即软删+彻底清除，同一台机器连跑两遍结果一致
- SKIP 是显式声明的缺口（缺凭据、缺 docker CLI、需破坏密钥的场景），不计入红绿
- 断言只比较确定性字段；requestId 等随机值排除在比较之外
