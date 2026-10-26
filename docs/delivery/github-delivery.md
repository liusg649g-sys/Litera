# Litera 翻译与笔记 GitHub交付准备

时间：2026-10-26T21:41:30+08:00（北京时间）。当前已完成人工验收的功能不再重做；本轮是交付兼容补丁、测试及提交前准备，不执行共享仓库写入。

## 1. 分支、远程及冲突

- 本地已创建并切换`delivery/translation-notes-20261026`，HEAD保持`947dc3cc6381ce4b19d587762950f381b6e31100`；main和历史开发分支保留，没有reset/clean/覆盖或提交。
- 普通fetch首次连接重置，HTTP/1.1限时重试成功获取main。原fetch只跟踪main；全分支fetch/ls-remote随后失败，未把失败当成功。
- 无凭据[官方GitHub分支API](https://api.github.com/repos/liusg649g-sys/Litera/branches?per_page=100)补查成功：**当前可见分支仅main**，SHA同上。没有已发布的其他分支新功能可比较；成员未推送的工作不能由此判断。
- main最近5次：947dc3c（2026-10-20阅读器/账号更新）、d95f3e3（10-16绘制/形状/插入）、9b15ff2（同模块WIP）、cc80b2a（文字批注）、240b9f3（文字批注WIP）。本地HEAD与远程main零提交差异；所有交付代码在工作区。
- 本次没有新main代码需要合并或同文件冲突要解决。未来高冲突点为main.py/models.py/documents.py、ReaderPage.vue、reader/context/navigation、公共DTO及0007/0008迁移；发布前必须再fetch/确认主线，不能依赖今天的零冲突。

## 2. 应提交和不应提交

完整逐文件清单：**[commit-files.txt](commit-files.txt)**。包含已验收的翻译/个人模型/笔记/来源/搜索/AI保存适配、0007/0008、前后端测试、运行脚本、必要依赖和文档。大部分是此前本地开发积累，不能全部说成本轮新增。

不应提交清单：**[excluded-files.md](excluded-files.md)**。本机AGENTS.md、LOCAL_DEVELOPMENT.md、compose.dev.yaml保留本地；真实.env、数据库/PDF/资产、密钥与用户密文备份、venv/node_modules/dist、缓存/日志/录屏/冷备都不纳入。不要git add .或-A。

`scripts/audit_delivery.py --write-manifest`只扫描Git候选文本，生成逐文件SHA256、模式与赋值检查、忽略验证和两组pathspec，不读被忽略的真实凭据/数据库，也不暂存。结果在`.cache/github-delivery/security-audit.json`。这不是全Git历史泄露审计、渗透测试或供应链安全认证。

## 3. 本轮实际修改和保留

| 范围 | 本轮新增/补充 | 兼容性 |
|---|---|---|
| model_secrets/config/user_models | AES文件Vault、非秘密模式/路径配置，旧存储方案不匹配时不显示已验证；保留DPAPI | 复用0008，既有Key不转换，Windowsauto不变 |
| AiModelSettings | 加密说明从Windows专用改为通用后端描述 | 不变更已验收交互 |
| Compose/ignore/example | 传递AI_*与legacy fallback/个人开关；可选外部secret；两实际构建上下文排除私密及产物 | 默认不启用个人模型；管理员显式配置后开启 |
| requirements.in | 补齐已锁定的既有运行依赖；AES用现有cryptography | 没有安装新依赖/升版本 |
| scripts | init_model_key.py、verify_delivery.py、audit_delivery.py | 独立随机文件/临时数据库，输出不含Key；构建不覆盖在线dist |
| 测试 | test_model_secrets、test_delivery_compatibility、临时AES浏览器fixture；5份Playwright配置和跨平台命令helper/3单测 | 不依赖Windows硬编码路径；实际Linux执行仍未验证 |
| 文档 | 当前README/03/04/07进度、公共API澄清、部署/团队接口、PR说明与交接 | 原历史记录保留，不把旧未勾选判成功能缺失 |

原`backend/app/documents.py`已有两项差异均保留：DTO增加attachment.sha256供来源身份核验；db.refresh(doc)时间戳候选。后者本轮未新增或扩大修复，真实MySQL仍待验，提交前须用户明确审阅，不能随便整文件还原而删除来源字段。

## 4. 安全存储与迁移

原Windows DPAPI未变；新LinuxAES-256-GCM方案使用仓库/数据库外的随机32字节base64主密钥文件、每次12字节随机nonce、owner+用途AAD及完整128bit tag，密文scheme为aes256gcm-file-v1。错误文件/宽POSIX权限/坏密文拒绝，不明文回退；旧DPAPI格式不匹配拒绝调用，只有本人显式重填才写新Key。本轮仅在临时SQLite备份/恢复副本使用合成密钥验证。

0007/0008新增表顺序不变，无0009或既有库迁移。普通Docker默认关闭个人设置，Linux启用时须正确配置可选secret并核对实际文件权限；不只看Compose.mode声明。POSIX真实权限检查在Windows跳过，目标Linux/Docker仍需管理员验收。详见[部署](deployment.md)。

## 5. 本轮实际测试与未验证项

| 范围 | 结果/环境 |
|---|---|
| 全量后端（含AES） | 452通过、1跳过；临时SQLite/Mock，POSIX权限需Linux |
| 新库/方言/依赖补充 | 3通过；SQLite从空库到0008及重复head，MySQL仅离线DDL，直接依赖与锁一致 |
| 前端 | 218通过；31文件，新增3个跨平台命令测试；类型检查通过 |
| 前端生产构建 | Vite构建子进程退出0，独立cache输出；未覆盖5183/dist |
| 浏览器 | 65通过、2私人PDF opt-in跳过；12笔记、28翻译/原C1/C2/全屏、17来源/生命周期/AI保存、3模型、5统一。入口适配后另做五配置--list与统一5项/三类入口smoke重跑，不重复加数 |
| 静态/格式 | 两份Compose YAML未插值语法解析、03/04/07 OpenSpec严格校验、git diff --check；实际最终输出见本轮交接 |
| 现有环境 | 5177/5180/5183数据库/PDF哈希和完整性一致，5183健康200；未重启或迁移 |

不重复计算定向和重跑：**738通过、3跳过**。自动化为合成数据与受控HTTP，不是真实模型/真实QA。用户已声明原5183五项人工验收全部通过；本轮没有读取真实Key、发模型请求或重新要求验收已完成核心。

中间测试设施问题已修正：验证驱动CP936打印失败（构建子进程实际成功）；新增Node helper在happy-dom提前解析URL、脚本名转换漏e2e数字导致启动失败；安全扫描器把Vue :key/data-source-highlight-token误判凭据。未改业务逻辑以放宽测试，未把中途失败写成通过。原始日志和退出/磁盘数据在`.cache/github-delivery/`，仅本地保留。

**未验证**：Linux镜像构建/原生依赖与POSIX实际挂载权限，真实MySQL/P0精度与锁，真实QA权威服务，具体网关逐次HTTP/质量/费用。Root依赖已锁，Rolldown Linux musl/GNU可选绑定存在，但Windows构建不代表Alpine成功。当前限流为单进程，不是多副本共享限流；主密钥轮换/KMS/跨主机真实Key迁移未实施。

## 6. 建议提交划分与PR

建议同一PR内两次提交，代码/测试互相依赖的部分原子交付，不拆成互相缺接口的翻译/笔记半成品：

1. `feat: deliver literature translation and notes with secure user models`：manifest中除README/HANDOFF/docs/openspec外的运行代码、测试、迁移、依赖、脚本、Compose/示例和ignore。包括既有P0候选，需用户最终审阅。
2. `docs: document accepted modules and team integration boundaries`：README/HANDOFF/docs/openspec。历史用户验收、Mock、真实QA和MySQL边界清楚。

两组精确pathspec已生成到`.cache/github-delivery/commit-runtime.txt`与`commit-docs.txt`，只是文件清单，**没有执行git add**。若希望一次原子commit，也可用完整commit-files.txt；两种方案均需最终批准。

拟PR标题：**feat: 交付文献翻译与笔记及安全个人模型配置**。
完整拟正文：[PR_DESCRIPTION.md](PR_DESCRIPTION.md)。base=main，head=delivery/translation-notes-20261026。没有创建实际PR或给组员发送消息。

获最终批准后才可执行以下未来步骤（本轮均未执行）：

```sh
git fetch origin
git rev-parse origin/main
python scripts/audit_delivery.py --write-manifest
git add --pathspec-from-file=.cache/github-delivery/commit-runtime.txt
git diff --cached --stat
git diff --cached --check
git commit -m "feat: deliver literature translation and notes with secure user models"
git add --pathspec-from-file=.cache/github-delivery/commit-docs.txt
git diff --cached --check
git commit -m "docs: document accepted modules and team integration boundaries"
git push -u origin delivery/translation-notes-20261026
```

确认PR正文后可在GitHub网页创建，或使用已配置的gh并以`--body-file docs/delivery/PR_DESCRIPTION.md`提交；不在shell内拼接多行正文。**合并需单独确认**，不自动merge或强推。若origin/main变化，停止发布，先在交付分支分析接口/迁移与文件冲突，获授权再集成并重跑受影响测试，不能覆盖主线。

## 7. 组员拉取与联调检查点

批准发布后，优先全新普通clone（不要--single-branch），再fetch并建立本地review分支跟踪远程交付分支；原克隆只跟踪main的组员可显式`git fetch origin delivery/translation-notes-20261026`后从FETCH_HEAD创建本地review分支，不强制覆盖其工作区。当前仓库的fetch配置本轮未修改。之后安装锁定依赖→按[部署步骤](deployment.md)建立全新独立项目/卷与主密钥→核验迁移/健康/依赖/安全Vault→注册自己的账号→个人模型主动测试→PDF翻译→笔记保存/搜索/来源高亮→双账号权限复核。不要把本机数据库/PDF/密钥备份提交后让组员拉取。

[团队接口](team-integration.md)明确06的UUID回答ID/整数修订、单文献权威引用、05的版本化chunk、三目标保存、CAS/幂等/草稿和模型capability边界。真实QA未交付不阻塞03/04交付，但不能标真实QA联调通过；不得自行重写RAG/提取。下一迁移编号须双方协调，0007/0008已使用。

本轮停在提交前；等待用户审批commit/push/PR方案。原已验收5183继续运行，Windows兼容补丁不热加载，当前无需重启用户环境。
