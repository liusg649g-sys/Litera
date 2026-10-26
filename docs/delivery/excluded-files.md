# 不应提交的文件

以下保留在本机，不删除：

- `AGENTS.md`：本机协作规范包含固定交接路径，保留本地，不直接共享。
- `LOCAL_DEVELOPMENT.md`：本机历史启动/数据说明，团队使用docs/delivery/deployment.md。
- `compose.dev.yaml`：本机litera-dev隔离配置，不用于团队默认部署。

已由忽略规则排除：真实.env及变体、数据库与伴随文件、PDF/图片storage、.cache、会话文件、用户密文备份/主密钥文件、node_modules、venv、dist、日志/录屏/测试输出、现有冷备和其他项目。只审查Git候选，不读取上述私有文件。

不要git add .或git add -A；获最终批准后按commit-files.txt明确暂存，并重新检查暂存区。扫描是模式检查与文件审阅，不宣称全历史/渗透测试。
