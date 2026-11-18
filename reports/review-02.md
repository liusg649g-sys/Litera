# 评审记录初稿 · review-02 · 依赖审计

**状态**：初稿，待人工复核并定稿。

## 用什么手段查

- AI 自审 + 脚本：`make check-security` 中的 SEC-06，进入 api 容器运行 `pip-audit`。
- 原始输出：`reports/dep-audit-before.txt`、`reports/dep-audit-after.txt`；例外登记：`reports/security-baseline.md`。

## 查了什么

- Python 运行期依赖的高危/严重漏洞，以及基础镜像自带 `pip` 的构建期通报。
- 重点核对鉴权、PDF 解析、HTTP 客户端、加密相关包是否命中 CVE。

## 判据

- 运行期依赖不得有未登记的高危或严重漏洞。
- 构建期 `pip` 通报必须按“包名 + 版本 + CVE + 不可达原因 + 缓解措施”登记，才允许通过。
- 新增依赖必须同步更新锁定文件，不能只在本地环境升级。

## 结果

- 通报由 104 条降至 12 条；剩余 12 条全部是基础镜像 `pip 25.0.1` 的构建期通报，已登记。
- `certifi` 2024.8.30 → 2025.8.3，`pypdf` 5.9.0 → 6.1.3，`Pillow` 11.3.0 → 12.0.0；后续又把 `dnspython`、`opentelemetry-api` 升到修复版本。
- 重新执行 `make check-security` 后 SEC-06 为 PASS。

## 未覆盖与人工复核

- 该审计只看 Python 依赖，不覆盖前端 npm 依赖与基础镜像 OS 包。
- 构建期 `pip` 只影响构建工具链，不在运行期请求路径；该判断需人工复核后保留为例外。
