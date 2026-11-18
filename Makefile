.PHONY: check-security check

COVERAGE_MIN ?= 80

# Security gate: SEC-05 secrets + SEC-06 dependency audit + SEC-07 escaping
# + SEC-02/03/INJ dynamic counter-examples.
# Exit 1 = FAIL, 2 = BLOCKED (stack/credentials missing), 0 = PASS.
# Without make: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1
check-security:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_security.ps1

# Non-security gate: 接口入口 / 业务逻辑 / 数据库 / 公共函数 / 错误处理 / 性能.
# Runs isolated SQLite unit/migration/query/audit tests first, then the real
# Compose apitest suite when the stack is reachable.
#   make check FILTER=docs-*       只跑某组接口用例（隔离测试仍全量）
#   make check COVERAGE_MIN=75     临时放宽覆盖率门禁（需在报告中说明）
# Exit 1 = FAIL, 2 = BLOCKED, 0 = PASS.
check:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_all.ps1 -Filter "$(FILTER)" -CoverageMin $(COVERAGE_MIN)
