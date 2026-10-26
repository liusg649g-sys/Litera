# P3-D1：AI回答保存笔记的独立适配

2026-10-26；分支`local/litera-dev-20261020`，HEAD `947dc3cc6381ce4b19d587762950f381b6e31100`。本轮完成笔记侧和隔离Mock，真实QA仍无可调用实现；D2未开始，人工验收待用户完成。

## 实现与兼容性（静态源码检查）

1. `backend/app/answer_sources.py`：`AnswerResolver`请求级服务接口、`ResolvedAnswer`/`AnswerCitation`边界及默认不可用实现。只读取权威记录，不生成/持久化问答、不读取模型配置。适配器须核对用户归属、当前修订、不可变证据/解析版本/chunk绑定；`AnswerResolutionError`只映射有限公共码，任意上游异常转安全503，不返回异常文本。
2. `note_captures.py`：既有`POST /api/v1/notes/captures`增加判别分支ai_answer；输入仅回答ID、修订和历史/未核实确认。`checked_answer`再核对文献权限、数据库与实际PDF字节SHA256、版本、引用页及原文。新增受保护的笔记侧`GET /notes/answer-preview/{answerId}?revision=N`；不是Change06规划的QA接口。
3. 独立块存储`question/answer/answerRef/contextDocument/evidenceState/citations/historical/uncitedAcknowledged/requestFingerprint`。所属文献与引用独立于M:N关联。生成答案不是PDF原文；无引用无页码，经明确确认才允许标记“未核实”。引用失败、服务错误、越权、过期不能降级。沿用operationId、现有笔记CAS和限额；同笔记同回答修订去重200且不恢复已解除的关联。
4. `SaveToNoteDialog.vue`和`captures.ts`复用新建/当前/其他目标、冻结来源、权威预览、显式关联、历史确认、同操作重试和冲突重读。`ReaderPage.openCapture`继续调用`prepareForInsert`/`afterCapture`，不另造自动保存；错误预览不会再被目标读取清空。
5. `AiAnswerNoteBlock.vue`显示问题、AI回答和独立引用/Mock/未核实标记；引用通过`NoteSourceLocation`复用NotesPanel.openSource和C2-A的文献ID+哈希+页码导航。无PDF.js textRanges，不宣称精确高亮；旧PDF块仍使用B1。`notes.py::_search_note`增加AI问题/回答/引用原文搜索，保留原字段。
6. `notes.sources`既有JSON/source_schema_version=1和0007完全复用；无模型、表、索引或迁移修改，无新依赖。旧版本遇到新块可保留未知内容；正文与结构化块仍独立保存。真实MySQL未运行，不以SQLite代替MySQL证据。

## 固定Mock的边界

`scripts/mock_answer_fixture.py`只提供固定模拟问题/回答和已知合成PDF。仅在APP_ENV=test、获准独立SQLite/PDF路径、空模型配置下由两个隔离启动脚本显式启用。默认应用不注册测试路由。Vite预览标志和后端isolatedMock同时成立才显示`MockAnswerPreview.vue`；不是实际AI问答面板。

隔离专用路径`GET /api/v1/notes/mock-answers/fixture.pdf`与`/list?documentId=...`需登录，普通应用不存在。启动不创建账号、文献或问答。用户须主动下载并上传合成PDF；对原有论文列表返回空，不伪造真实论文引用。回答ID由owner/document/固定案例派生，无问答表。来源核验成功仅表示合成PDF的固定引用正确，不表示科学结论或真实RAG已验证。

待06负责人确认：稳定ID/修订及作废规则；认证owner和文献归属；问题可空/摘要模式；回答有效期和contextRevision；05解析版本/chunk/quote的权威验证；服务错误码、实际读取方式及多文献回答范围。D1只支持单文献引用，内部DTO是本地暂定适配协议。

## 实际自动化证据

- 后端：最终从不含.env的临时cwd执行`python -m pytest .../test_ai_note_captures.py .../test_note_captures.py .../test_notes.py .../test_note_search.py .../test_notes_migration.py .../test_translations.py -q --tb=short --maxfail=1`，**140通过，0失败**，57.48秒；其中D1 27项。TEST_DATABASE_URL关闭，独立临时SQLite/PDF/导出目录，清除继承AI_/TRANSLATION_变量；临时Alembic配置使用Windows locale编码。真实模型调用0，MySQL未执行；迁移用例仅临时SQLite及MySQL离线DDL。
- 前端：`npm test -- --run`最终**27文件199项通过**，27.44秒（D1新增9项）；`npm run build`含vue-tsc类型检查通过，Vite 3.16秒。既有大chunk警告保留，未扩展重构。
- 浏览器：`node node_modules/@playwright/test/cli.js test --config=playwright.note-captures.config.ts`，**16通过/1跳过/0失败**，1.5分钟。使用5182/8005、临时SQLite、真实PDF.js/合成PDF、固定Mock和明确网络故障注入。D1三项覆盖新建/当前/其他目标、草稿flush、去重、无引用确认、服务故障重试/核验失败禁保存、搜索/引用页跳转、刷新/重新登录。13项既有来源保存/乱码保护/翻译/来源导航/高亮回归通过；私人PDF可选案例未启用而跳过。
- 浏览器wrapper每2秒检查C/D空闲空间，小于10,000,000,000字节只终止其自有测试进程树；两次完整回归最低D盘均高于阈值。未修改既有预览保护机制。

### 失败和修正记录

首轮后端72通过/2失败/26setup错误：Mock记录漏answer字段、测试辅助函数/route检查及setup失败后的依赖清理问题；修正后定向22通过/5失败，严格PDF核验发现合成样本在词中间强制换行，修正样本后103项回归通过，未放宽核验。首轮类型检查发现PDF专用测试/返回类型需要显式收窄，采用泛型后通过。

首轮D1浏览器1通过/2失败：刷新测试等待不足，及当前笔记目标读取清空来源预览错误；修正后D1三项通过。扩展浏览器15通过/1失败/1跳过：测试期间热更新发生DOM重置/超时；源码稳定后完整重跑16通过/1跳过。热更新是现场与修改时序支持的原因，不推断业务数据异常。

最终扩大后端回归的临时启动包装曾因UTF-8临时ini与Alembic的Windows GBK读取不一致产生140项setup错误；改为locale编码后127通过/1失败（空AI环境变量覆盖旧测试的合成.env配置）；清除继承变量、保留APP_ENV=test与空白cwd后140全部通过。以上为测试包装问题，无业务配置、测试断言或业务数据库改动。

## 预览加载与人工验收

5180原实例因10GB磁盘保护停止（读取现有日志确认），清单已自动移除；未强停或绕过。确认端口空闲、无活跃预览PID、0007一致、完整性ok、过期资产及导出清理候选为空后，将整个预览目录作唯一联合备份，45文件12,821,277字节，相对路径/大小/SHA256完全一致，备份数据库完整性ok/FK0。完整本地位置和数据指纹见统一LITERA_HANDOFF第49节，不在仓库公开本机敏感配置。

只执行一次`./scripts/notes-preview.ps1 start`成功。5180首页、代理健康与8003健康均200；新适配API/隔离测试路由和Vite模块可读取。原有全部业务表行指纹、账号/文献/笔记/关联/来源数量与2个PDF哈希不变。未登录预览进行写入验收，未新增测试账号或文献。5177未访问或修改，Docker/CampusClaw/真实模型均未操作。

人工验收地址：http://127.0.0.2:5180/ 。使用原隔离预览账号登录，打开任意文献，展开“模拟问答保存验收（非真实AI）”，下载合成PDF并手动上传，再打开该合成文献。分别将引用回答保存到新建、当前和其他笔记，检查Mock标识/独立引用、重复不追加、正文不丢；无引用回答在确认前不可保存，确认后显示未核实且无原文跳转。刷新/重登检查快照保留。测试操作会在5180新增合成文献/笔记，不操作原有数据。

验收后停止；真实QA联调D2、真实MySQL、5177迁移及旋转/跨页增强均未开始。
