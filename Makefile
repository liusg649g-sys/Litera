.PHONY: check-security check

# 覆盖 SEC-05（密钥扫描）与 SEC-06（依赖审计）；无 make 环境时可直接执行：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1
check-security:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1

# 业务验收跑批：黑盒打真实 Compose 服务（需先配置 apitest/config.local.ps1 或 APITEST_* 环境变量）
#   make check FILTER=docs-*   只跑某组
check:
	powershell -NoProfile -ExecutionPolicy Bypass -File apitest/run_checks.ps1 -Filter "$(FILTER)"
