> 2026-10-26状态更新：用户已确认统一5183五项人工验收全部通过，翻译与笔记开发验收完成。本文后续“等待验收/停机”等是对应历史时点；当前GitHub提交前准备、Linux兼容补丁和测试边界见docs/delivery/github-delivery.md，不能把历史状态当当前运行结论。

# Litera 文献翻译与笔记统一交付

记录时间：2026-10-26 20:06:47 北京时间。本报告描述当前本地未提交版本，不能用旧GitHub任务勾选替代当前源码或运行证据。

## 1. 唯一人工验收入口

**http://127.0.0.3:5183/**，已运行。登录页、设置页静态入口、首页、/api/v1/health 均HTTP200；不存在的API返回404。实际Chromium打开首页转入/login，登录按钮和统一验收横幅均可见。可使用原5180预览账号的邮箱和密码；本轮未读取、输出或重置密码，也未新建实际站点账号。也可自行注册此独立副本的新账号。

前端生产构建由同一个FastAPI工作进程提供，取消此站常驻Vite/Node和8004代理。另有轻量Python守护及Windows虚拟环境包装进程；不是零守护的单一OS进程。正常服务会持续运行至手动停止或触发原10GB磁盘保护。

在项目根目录使用：

```powershell
.\scripts\litera.ps1 status
.\scripts\litera.ps1 stop
.\scripts\litera.ps1 start
```

start先检查现有实例，再构建/准备/检查/启动，已有实例或半成品副本会拒绝；不要反复启动或手动删除清单绕过检查。脚本复用现有Python/Node依赖，未安装第二套环境。新站数据目录为`.cache/user-model-preview/unified`，与先前空的`.cache/user-model-preview`根数据库及原5177/5180目录都隔离。

## 2. 已实现功能与证据边界

| 功能 | 当前行为与主要实现依据 | 本轮证据 |
|---|---|---|
| 词/句/段落双向翻译 | TranslationPanel/createTranslation；POST /documents/:id/translations；手动按钮、实时500ms、去重/串行最新待处理请求、旧结果失效 | 前后端及真实PDF.js浏览器，模型为Mock |
| 原文/译文与来源 | 原文保留，页码/文献ID/方向/上下文；乱码阻断，断词仅可靠布局证据；复制及剪贴板失败、超时/限流/重试 | 单元/后端/浏览器 |
| 用户模型 | /settings/ai；本人一套配置，保存/保留或更换/清除密钥、测试、删除、CAS修订 | 控制HTTP替身、临时SQLite、Windows DPAPI及浏览器 |
| 显式模型模式 | /user-model/options提供服务端可用模式；本站默认Mock，主动选择个人模型才调用；选择本身不请求；按账号sessionStorage仅存模式 | 新增统一面板单元、统一浏览器 |
| 多对多笔记 | 新建编辑删除、解除关联与删除分开；标题正文自动保存/CAS/失败草稿/完整关联集合 | 完整后端及笔记浏览器 |
| PDF/当前译文/历史译文保存 | 复用SaveToNoteDialog三目标、显式关联和历史确认、来源块、服务端PDF核验、签名与幂等 | captures及统一浏览器 |
| 关键词搜索 | 标题/正文/PDF原文/译文/已保存AI问题回答；本人范围、字面匹配、防抖/去重/安全命中高亮 | 搜索单元/API/浏览器 |
| 来源页导航与临时高亮 | ID+PDF SHA256+物理页；复用navigateReader/ReaderPage/PdfPage/sourceHighlight，校验PDF.js文本项与UTF-16范围；单行/跨行/缩放，缺少可靠范围仅跳页 | 合成真实PDF.js浏览器 |
| 笔记生命周期与权限 | 跨账号隔离，文献软删除/恢复/永久删除、关联解除后独立来源不改写、不误删其他文献的笔记 | 临时SQLite生命周期及浏览器 |
| AI回答保存适配 | 服务端AnswerResolver、ai_answer独立块、权威记录/引用核验、无引用明确确认未核实、三目标/CAS/幂等 | 固定Mock记录、合成PDF；不是实际AI问答 |

P2/P3既有人工验收是用户提供的历史证据；本轮新增统一版本、个人模型及当前部署仍待用户统一验收。真实QA是唯一尚未交付的业务接口外部依赖；本轮未开发RAG、问答存储或新的问答面板。

## 3. 模型设置和实际使用

1. 登录后从个人资料进入“AI 模型设置”，或直接打开`/settings/ai`。
2. 服务类型选OpenAI Compatible，填写自己的公网HTTPS Base URL、实际对话模型名称及Key。候选`https://ai-gateway.devops.hello1023.com/v1`和`course-chat`来自用户，**本轮没有验证其可调用性**。
3. 保存不会请求模型；点击“测试连接”才由后端发一个固定短提示，最多32输出Token、15秒总时限、每人每分钟最多3次、全局2并发。成功后此修订才标为已验证。修改地址/模型/Key会撤销验证。
4. 打开PDF→翻译面板→“翻译模型”明确选择“我的模型”；确认面板显示个人模型名称，再选正文并点击翻译。默认Mock不是翻译质量验收；个人模式失败不会回退Mock或开发者Key。
5. 模式选择按账号保存在当前浏览器会话，重新打开设置再返回阅读器也保留；不存在个人配置时提示“模型未配置或尚未验证”。切换配置或选区使迟到结果失效，历史结果保留自身来源。

**用户明确选择只在网页自行填写并测试。此次真实模型请求0；未读取backend/.env，未替用户填写任何Key或消耗个人/开发者额度。** 两方向、错误Key、模型404、超时、限流、异常响应自动化均为受控替身，不是实际服务商验收。

## 4. 密钥、权限和网络安全

- Windows DPAPI CurrentUser封装（model_secrets.WindowsSecretVault），用途+Litera用户ID绑定。主密钥由Windows账号管理，数据库仅保存认证密文、方案标记及配置修订；无明文回退。Windows账号/主机改变需重新填写Key；将来Linux部署必须提供独立安全Vault适配器。
- 查询只返回模型/地址/hasApiKey/verified/revision，不回显Key；输入框保存后清空；按当前session读取本人配置，不接受客户端owner。保存和删除有CSRF与CAS；探测和翻译结束复核配置修订。
- model_network.validate_base/resolve_public/PublicNetworkBackend：公网HTTPS443、禁止本机/私网/元数据/歧义IP/凭据与查询参数；实际连接时检查全部DNS结果并连接已验证数值IP，TLS保留原主机名SNI及CA校验；禁止重定向、代理、Unix socket与自动重试。测试不是任意网络代理。
- 统一站禁用developer调用，旧开发者实现/配置保留。个人请求只使用所属配置；结果中若上游回显Key将被拒绝，固定错误代码/文案不返回上游正文或堆栈。
- Mock和真实通路回执按请求区分isolated_mock/model_api，签名绑定该标记、owner、PDF哈希、文献、页码、原文/译文/方向；互换标记会失败。Mock回答与Mock译文都明确展示，不伪造可信真实AI。
- `.env`、`.cache`、数据库、dist和运行环境均被Git忽略；实际执行git check-ignore已确认backend/.env、统一数据库、dist/index.html。没有输出或记录密钥内容。

## 5. 数据、备份与迁移

原5180保持离线且0007；5177未启动、迁移或写入，其真实配置与数据库未读取。新副本由5180完整备份恢复，不是重新初始化空站。

联合备份：`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\unified-source-20261026-195350`。**54文件、12,840,357字节**，包括数据库/PDF/会话文件/历史日志及原目录其他文件，源与备份相对路径、大小、SHA256逐一相同；副本恢复校验通过。备份包含敏感会话文件，仅本机保存，不上传或提交。

- 备份前源库无非空WAL/journal；离线端口检查通过。源/备份/恢复副本完整性ok、外键错误0。
- 仅副本升级既有增量`0008_user_model_profiles`（此前已实现的迁移，本轮不新增编号）。新增owner主键、revision、provider、base_url、model、encrypted_key、encryption_scheme、tested_revision、updated_at；不改原笔记/文献表。临时库实际备份恢复、迁移及重复执行测试通过。
- 启动前清理候选0，独立TMP无导出工作区。正常API仅操作新副本的资产与独立TMP；启动不做新迁移。半成品缺少import-verification或版本不符禁止启动；失败保留现场，不自动覆盖恢复、不降级。
- 源与副本均1账号、3文献/3PDF、7笔记、12关联、6来源块、0图片资产。副本个人配置数0，等待用户自行填写。
- 原源库任务开始时users/documents/document_files/notes/note_documents/reader_assets/annotations逐表指纹及全部PDF哈希终审一致；副本旧表和PDF在迁移/启动后也保持一致。原有用户内容未修改。
- 原5177/5180未启动、未迁移、未写入；本轮不操作Docker/其他项目/Windows设置。原10,000,000,000字节门槛保持，API每0.25秒、守护每5秒检查空间，低于阈值正常退出、不自动重试。

## 6. 本轮实际测试

| 范围 | 实际结果 | 环境 |
|---|---|---|
| 全部后端22测试文件 | **443通过，0失败，0跳过** | 临时SQLite/PDF/TMP、禁止外网、Mock模型 |
| 前端30测试文件 | **215通过，0失败** | Vitest/happy-dom，单worker |
| 统一站新增浏览器 | **5通过** | 单FastAPI静态站+真实Chromium/PDF.js+临时SQLite+受控HTTP |
| 既有笔记浏览器 | **12通过** | 临时SQLite |
| 既有翻译浏览器 | **11通过、1跳过** | 合成PDF、Mock模型；未提供私人PDF opt-in |
| 来源/QA/生命周期浏览器 | **17通过、1跳过** | 临时SQLite+Mock，未提供私人PDF opt-in |
| 既有用户模型浏览器 | **3通过** | 受控HTTP Mock、临时SQLite |
| 类型检查与生产构建 | **通过** | vue-tsc --noEmit、Vite8.3.4，Node堆1GB |
| 实际部署 | **首页/登录/设置入口/健康200，未知API404，Chrome登录可见** | 独立副本5183，无真实调用 |
| MySQL/真实QA/个人真实模型 | **未执行** | MySQL/QA依赖暂缓，个人真实验证留用户网页 |

总计不重复计算**706项通过、2项跳过、最终0失败**；早期51项针对性通过已包含全部443后端内，不另加。实际站登录页检查也不混入706计数。浏览器的“真实PDF.js/HTTP”不等于真实模型；混合来源测试中的model_api分支由受控HTTP产生，测试数据不进入最终站。

关键命令（工作目录项目根，浏览器内部cwd frontend；隔离驱动均清除AI环境并监测10GB）：

```powershell
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_backend.py unified-backend-all <全部backend/tests/test_*.py文件名>
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_front.py unified-front
.\backend\.venv\Scripts\python.exe scripts/user_model_preview.py build
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_browser.py unified
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_browser.py notes translation captures user-models
.\backend\.venv\Scripts\python.exe scripts/user_model_preview.py prepare
.\scripts\litera.ps1 start
```

原始日志、JUnit与退出/最小磁盘记录：`.cache/user-model-work/unified-backend-all.*`、`unified-front.*`、`browser-*.log/*-run.json`；统一备份/迁移清单`.cache/user-model-preview/unified/import-verification.json`，启动日志同目录api/supervisor带时间戳；终审`.cache/final-delivery/final-audit.json`、deployment-check.json，登录截图unified-login.png。

中途失败已修正并保留证据：静态SPA未知API错误200及Windows分隔符/根路径兼容（前三批依次49通过/1失败、49通过/1失败、50通过/1失败，最终51全部通过）；新增测试三处DOM value类型标注导致首次类型检查失败，补标后类型/构建通过；Git终审初次混用分组与完整未跟踪清单产生误报，改为-uall确认全部原路径仍在。无降低断言、放宽权限或来源检查。最终非失败提示：Starlette TestClient/httpx弃用提示、Node颜色变量提示、Vite阅读器包大于500kB提示。

## 7. 本轮文件和关键函数

本轮修改既有实现：config.Settings；translations.TranslationInput/translate；translation_proof.issue_translation_proof/verify_translation_proof；user_models.create_user_model_router新增options；TranslationPanel.loadUserModel/changeModel/resultCurrent；reader/translation.createTranslation模式校验；App横幅；ReaderPage隔离工具入口；mock_answer_fixture.enable_mock_answers；user_model_preview.prepare/build/check/api/serve_api/supervise；user-model-preview.ps1。

本轮新增业务/运行文件：backend/app/acceptance_site.py（mount_acceptance_site/AcceptanceFiles）、translation_modes.py（translate_mock）；scripts/litera.ps1；unified_e2e_server.py（仅临时测试）。新测试：test_unified_acceptance.py、unified-translation-panel.test.ts、unified.spec.ts、playwright.unified.config.ts；补充test_user_model_preview.py、user-model-translation.test.ts。文档：README/HANDOFF、Change03/04进度澄清、Change07设计/规约/任务与本报告。

复用而非重写：ai_service/model_service、model_network、model_secrets、user_models及迁移0008、AiModelSettings、notes/note_captures/answer_sources、NotesPanel/SaveToNoteDialog/NoteSourceBlocks/AiAnswerNoteBlock、PDF.js与reader navigation/sourceHighlight。backend/app/documents.py的既有P0候选修改保留，未触碰；不将SQLite通过视为MySQL验收。

## 8. 统一人工验收清单

以下操作仅影响新副本或用户下载；请使用新建验收笔记进行改/删测试，保留原有内容。

1. 登录→文献库：用原5180账号登录，应看到原文献/笔记；刷新或重新登录后仍在。记录错误文案和页面URL，不记录密码。
2. 设置（写个人配置/主动外部请求）：保存自己的地址/模型/Key→测试；保存无调用，Key不回显。修改后需重新测试，删除仅删本人配置，译文笔记保留。
3. 阅读→真实翻译（主动外部请求）：PDF英文选区→选“我的模型”→英译中；中文PDF选区→中译英。看模型名称、来源标题/页码、当前译文。控制请求次数；服务是否支持course-chat以实际错误或成功为准。
4. 实时/并发：开启实时后稳定选区约500ms才触发；收起暂停。更换选区/标签后旧结果不冒充当前；出现限流暂停，不自动无限重试。复制失败有提示。
5. 保存（写新副本）：当前译文→新建/当前/其他笔记；历史译文必须确认历史原文/来源。PDF原文“添加到笔记”形成独立块，不覆盖手写正文。刷新保留。
6. 笔记：新建两条；一条关联两篇文献；编辑自动保存；折叠重开；解除一篇关联保留另一篇及正文。删除只对新建验收笔记操作且先取消一次、再明确确认。
7. 搜索与定位：搜标题/正文/原文/译文，中英大小写及部分词，结果无重复；打开命中笔记→查看原文→准确PDF与页码，有可靠范围时单/多行临时高亮，缩放不漂移；缺范围只跳页。
8. 草稿与来源独立性：未保存正文时点击跨文献来源，草稿不丢、关联不变；历史来源不跟随当前标签改写。异常PDF显示保护提示，不伪造选区。
9. 模拟AI保存：阅读器“模拟问答保存验收（非真实AI）”→下载并上传合成PDF（或已有合成PDF）→保存模拟引用回答到三类目标；无引用回答必须勾选未核实确认，不出现伪造页码。这不是实际问答。
10. 重登复核：笔记正文、块、来源、关联不丢；已保存模型仍脱敏且按本人权限访问。真实模型质量、网关兼容与费用由此次主动测试确认。

## 9. 未完成/外部依赖/版本

- 真实QA尚未交付：保持默认不可用AnswerResolver和契约v1，待06负责人提供owner绑定answerId/revision/权威引用核验。不能把Mock联调当真实完成。
- 新个人模型真实调用待用户网页测试（用户明确选择），不是代码缺少适配；本轮未实际核实course-chat/网关兼容、实际限流或翻译质量。
- 真实MySQL/P0与Linux Vault未验；SQLite迁移/Mock不能替代。旋转、跨物理页连续摘录/高亮、OCR与历史范围重建均按用户决定暂缓；可靠信息不足安全降级，不猜测。
- 当前分支`local/litera-dev-20261020`，HEAD`947dc3cc6381ce4b19d587762950f381b6e31100`；未切换、提交、推送或重置Git。原暂存区为空，已有未提交和未跟踪文件均保留；完整最终Git清单追加统一交接。本轮只新增统一交付所需文件及增量，不覆盖P0或成员原工作。

完成后保持统一站运行，等待用户统一人工验收；不自动进入真实QA/MySQL/旋转或其他模块。
