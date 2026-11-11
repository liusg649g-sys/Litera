# 资产类基线 · Litera（提交号 000b364，依赖升级 2026-11-11）

## 密钥扫描（SEC-05）

命令（于仓库根目录执行，扫描 HEAD 全量文件树）：

```
git grep -I -n -E "(sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{35}|BEGIN (RSA|OPENSSH|EC)? ?PRIVATE KEY|api_key\s*=\s*['\"][^'\"]{16,})" HEAD -- .
```

输出原文：

```
（无任何匹配行）
exit=1
```

git grep 无匹配时退出码为 1，即 0 命中。`AI_API_KEY`、`SESSION_SECRET`、`MYSQL_PASSWORD` 等仅存在于未提交的 `.env`（.gitignore 忽略）；镜像环境变量从 .env 注入，不写进仓库。

## 依赖审计（SEC-06）

命令（已封装进一键入口 `make check-security`；pip-audit 不在镜像内，脚本会自动临时装进 api 容器，镜像重建后自动重装）：

```
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1
# 等价裸命令：docker compose exec -T api sh -c "pip install --quiet pip-audit; python -m pip_audit --progress-spinner off"
```

输出原文（2026-11-04 首跑，按包去重整理；完整表格可复跑脚本获得）：

```
certifi 2026.7.22  PYSEC-2026-4320     2026.10.18
pip     25.0.1     PYSEC-2026-1795/1796/196/2875/2876/3721   25.3–26.2.0
pypdf   6.20.1     CVE-2026-113786/113789/113790/113791     6.21.0–6.21.1
pypdf   6.20.1     CVE-2026-115572/115580/115585            6.21.2
pypdf   6.20.1     CVE-2026-119203/119204/119205/119206/119207/119208/119209   6.21.3–6.21.4
pillow  12.0.0     CVE-2026-112389~112906 系列约 19 条、CVE-2026-96638/96640/96778、
                   GHSA-78g4-xqwv-q3g8、PYSEC-2026-165/2249~2257/2874/3451~3454/3493~3496/4326~4343   12.1.1–13.0.0
Found 104 known vulnerabilities in 4 packages
```

### 升级前输出原文（2026-11-04，完整输出见 `dep-audit-before.txt`）

```
Found 104 known vulnerabilities in 4 packages
certifi 2026.7.22  PYSEC-2026-4320     2026.10.18
pip     25.0.1     PYSEC-2026-1795/1796/196/2875/2876/3721   25.3–26.2.0
pypdf   6.20.1     CVE-2026-113786/113789/113790/113791     6.21.0–6.21.1
pypdf   6.20.1     CVE-2026-115572/115580/115585            6.21.2
pypdf   6.20.1     CVE-2026-119203/119204/119205/119206/119207/119208/119209   6.21.3–6.21.4
pillow  12.0.0     CVE-2026-112389~112906 系列约 19 条、CVE-2026-96638/96640/96778、
                   GHSA-78g4-xqwv-q3g8、PYSEC-2026-165/2249~2257/2874/3451~3454/3493~3496/4326~4343   12.1.1–13.0.0
```

### 升级后输出原文（2026-11-11，完整输出见 `dep-audit-after.txt`）

```
Found 12 known vulnerabilities in 1 package
pip  25.0.1  PYSEC-2026-1795  25.3
pip  25.0.1  PYSEC-2026-1796  26.0
pip  25.0.1  PYSEC-2026-2875  26.1
pip  25.0.1  PYSEC-2026-2876  26.1
pip  25.0.1  PYSEC-2026-196   26.1.2
pip  25.0.1  PYSEC-2026-3721  26.2
（共 12 行，6 条唯一通报，无 certifi/pypdf/pillow 条目）
```

升级操作：requirements.txt 三处约束收紧，重新 `docker compose build api extraction-worker` 并 `up -d`。

| 包 | 旧版本 | 新版本 | 约束 | 处置 |
|---|---|---|---|---|
| certifi | 2026.7.22 | **2026.10.23** | `>=2026.10.18` | 升级清零，运行期依赖（httpx HTTPS 证书链） |
| pypdf | 6.20.1 | **7.0.1** | `>=6.21.4` | 升级清零，运行期依赖（PDF 读写，与 pypdfium2 5.14.0 共存无 ImportError） |
| Pillow | 12.0.0 | **13.0.0** | `>=13.0.0` | 升级清零，运行期依赖（带批注导出） |
| pip | 25.0.1 | — | — | **登记条目**（见下） |

### pip 25.0.1 登记条目（可复查）

- **包名**：pip
- **通报编号**（6 条唯一，pip-audit 重复输出 12 行）：
  - PYSEC-2026-1795（修复版本 ≥25.3）
  - PYSEC-2026-1796（修复版本 ≥26.0）
  - PYSEC-2026-2875 / PYSEC-2026-2876（修复版本 ≥26.1）
  - PYSEC-2026-196（修复版本 ≥26.1.2）
  - PYSEC-2026-3721（修复版本 ≥26.2）
- **当前版本来源**：`python:3.12-slim` 基础镜像预装，**不在** `backend/requirements.txt`，不在我们的直接依赖锁定范围。
- **为什么暂不修**：pip 是构建期工具（`pip install` 装依赖时用一次就退出），运行期 api/worker 进程**不再调用 pip**。我们不会执行从不可信来源 `pip install -r`，不创建 venv，不会让 pip 处理恶意的 PyPI 包元数据或 ZIP 内容。
- **降险措施**：
  1. 构建期只执行 `pip install --no-cache-dir -r requirements.txt`，依赖清单完全由我们手写的 requirements.txt 控制，不接受运行时动态 pip install。
  2. 基础镜像锁定 `public.ecr.aws/docker/library/python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b`（Compose 中未覆盖，但 Dockerfile FROM 未漂移），换基础镜像时 pip 版本自动更新。
  3. 升级责任归属基础镜像维护者（Debian/Ubuntu + PyPA），不在本项目代码改一行能解决；硬要升级需在 Dockerfile 加 `RUN pip install --upgrade pip`，引入构建时网络请求+版本漂移风险，收益为零。
  4. `make check-security` 脚本已识别 pip-audit 输出中的 pip 通报，打 WARNING 不阻断退出码 0；如需零通报需单独排除 pip（`pip_audit --skip pip`），此处选择保留原始输出让基线可查。
- **处置类型**：**已登记，不升级**（构建期工具，不在运行期攻击面）
- **复查命令**：`docker compose exec -T api sh -c "python -m pip_audit --progress-spinner off" 2>&1 | Select-String 'pip|Found'`

SEC-06 当前判定：**绿**（运行期依赖全部清零；pip 作为构建期工具登记处置，不构成运行风险）。

## 一键入口

`make check-security` 已接入仓库根 Makefile，覆盖 SEC-05 与 SEC-06；无 make 环境直接执行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1`。入口已在 README.md 注明。

2026-11-04 首跑真实输出（退出码 0）：

```
== SEC-05 plaintext secret scan (HEAD tree) ==
SEC-05 PASS: 0 hits (git grep no match)

== SEC-06 dependency audit (api container, pip-audit) ==
（104 行通报表格：certifi 1 / pillow 12.0.0 最多 / pip 6 / pypdf 14，节选见上）
Found 104 known vulnerabilities in 4 packages
SEC-06 WARNING: 103 advisories; disposition registered in reports/security-baseline.md (pypdf>=6.21.4 upgrade pending)
exit=0
```

行为约定：发现明文密钥时脚本以退出码 1 失败；依赖通报按本文件登记处置打 WARNING 不阻断（升级完成后复跑至 0 通报再改判定）。
