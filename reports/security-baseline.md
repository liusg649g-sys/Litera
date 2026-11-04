# 资产类基线 · Litera（提交号 000b364，2026-11-04）

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

统计与处置登记（官方汇总行：`Found 104 known vulnerabilities in 4 packages`）：

- pip 25.0.1：6 条唯一通报（PYSEC-2026-1795/1796/196/2875/2876/3721），修复版本 25.3–26.2.0。pip 为镜像构建期工具，不在运行期攻击面；随 python:3.12-slim 基础镜像升级处理。
- **pypdf 6.20.1：14 条 CVE，修复版本 6.21.0–6.21.4。pypdf 是运行期依赖（题录提取读 PDF + 带批注导出写 PDF），处置：升级 requirements.txt 至 pypdf≥6.21.4 并重跑提取与导出回归后更新本文件 —— 待执行。**
- **pillow 12.0.0：输出中通报最多（去重后约 60 条，含 CVE-2026-112xxx/966xx 系列与 GHSA-78g4-xqwv-q3g8），修复版本 12.1.1–13.0.0。处置：升级至 pillow≥13.0.0 后复测 —— 待执行。**
- certifi 2026.7.22：1 条（PYSEC-2026-4320），修复版本 2026.10.18，随依赖升级处理。

SEC-06 当前判定：黄（四处通报均已登记，pypdf 与 pillow 为运行期依赖，升级前不算过）。

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
