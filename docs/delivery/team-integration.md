# 与文献信息提取、真实AI问答的团队集成

2026-10-26。仅核对当前源码和契约，不开发05/06。官方GitHub API本轮仅发现main，HEAD947dc3cc6381ce4b19d587762950f381b6e31100，无已发布的新分支实现；不能由此断言组员电脑里没有代码。

## 已存在与未交付

笔记侧已经存在`answer_sources.AnswerResolver/ResolvedAnswer/AnswerCitation`、`note_captures.checked_answer/answer_snapshot`及AI来源块/搜索/保存前端。真实解析器默认UnavailableAnswerResolver，`get_answer_resolver`是注入点；不是RAG/问答服务。Change06任务和旧AnswerDTO仅规划，当前不能向一个臆造的QA HTTP接口发请求。

已实现的笔记接口：

| 接口 | 权限/行为 |
|---|---|
| GET /api/v1/notes/capture-config | 当前会话，报告aiAnswerCapture.available/isolatedMock，不伪装真实QA |
| GET /api/v1/notes/answer-preview/:answerId?revision=N | current_session，服务端取权威快照，核验PDF/版本/引用，默认503未接 |
| POST /api/v1/notes/captures | Origin/CSRF，原子新建或追加、CAS、幂等和明确关联；source.kind=ai_answer时浏览器只传ID/版本/确认 |
| GET /api/v1/user-model、GET /options、PUT/DELETE、POST /test | 当前用户配置与显式连接测试；不支持读他人Key或把Key转给浏览器 |
| POST /api/v1/documents/:id/translations | 扁平text/pageNumber/contextRevision/sourceLanguage/targetLanguage及modelSource/modelRevision；响应source+translationProof，不是旧规划translationId |

## 06必须确认和提供的服务端记录

| 字段/能力 | 当前笔记适配要求 |
|---|---|
| answerId | 稳定UUID；不能用临时数组下标。若06采用其他ID，需要商定映射适配，当前不是已承诺协议 |
| answerRevision | 正整数>=1；发布后内容/引用不可变，修改产生新修订 |
| ownerId | 权威服务端绑定，不能接受浏览器自报归属 |
| documentId/fileSha256 | 当前有权限的原始文献ID及真实文件摘要，不能按标题猜测 |
| question/answer | 权威快照，问题最多6000、回答20000字符；AI文字与PDF原文分开 |
| status/evidenceState | answered或insufficient_evidence；verified必须有真实证据，none无可信引用且需显式确认 |
| provenance | model_api或isolated_mock，真实解析器不能发布伪Mock引用作为真实模型 |
| contextRevision/createdAt/expiresAt | 上下文修订、时间与失效规则，过期/撤销拒绝 |
| extractionVersion | verified回答必须绑定当前解析版本，与Document.extraction_version核对 |
| citations[] | 最多20个；citationId/documentId/fileSha256/extractionVersion/chunkId/pageNumber/quote；页码为1基物理页，quote<=6000 |
| resolve(db,owner,id,revision) | 自身授权、版本/过期/撤销校验，返回ResolvedAnswer，错误映射not_found/stale/expired/unavailable |
| verify_citation(db,owner,answer,citation) | 从版本化chunk/证据索引验证绑定，不能只相信模型自报页码或搜索到一处相似文字 |

**当前D1仅支持单文献回答**：所有citation的文献、文件哈希、解析版本必须与回答context文献相同。笔记本体仍M:N；这不等于多文献QA已经支持。如需跨文献QA证据，另行协议设计和测试，不放宽当前检查。

## 05提取模块配合

需要按documentId+fileSha256+extractionVersion读取可靠的页/chunk证据，明确重解析、删除/恢复、旧版本引用失效策略；对Document.parse_status/extraction_version/page_count的写入必须协调现有文献版本/CAS。不能静默替换已保存来源身份。笔记自己的PDF核验是二次防线，不应被当作05的持久化索引或06的证据绑定服务。

## 实际保存链路

1. 06在经过认证的问答界面显示已发布回答，发出与当前/历史状态一致的“保存到笔记”事件，仅冻结answerId/answerRevision及历史确认状态。
2. ReaderPage.openCapture复用NotesPanel.prepareForInsert/flush，避免800ms自动保存与插入相互覆盖；复用SaveToNoteDialog新建/当前/其他目标。
3. 对话框先请求笔记侧answer-preview，后端AnswerResolver取得权威快照；checked_answer核验owner、文献实际SHA256、版本、证据绑定、页码和PDF可提取文字。
4. 点击保存POST captures，服务端再次核验；来源块保存问题/回答、不可变answerRef和独立citations，CAS提交。浏览器不能提交所谓可信answer/quote来跳过服务端。
5. 无引用的合法none回答必须确认“未核实”，不生成页码或精确高亮；错误引用/越权/过期/服务故障拒绝，不能降级绕过。重复同回答修订不重复插入；重试复用operationId。
6. 来源页导航复用C2-A；AI引用没有经过PDF.js字符范围校验的坐标，只做可靠页跳转，不冒充B1精确高亮。

## 统一模型能否复用

`ModelProfile`、`ModelService.complete(messages,principal_id,profile)`和OpenAICompatible/安全网络/Vault可供未来QA复用；用户配置只存一份，不能另建全局共享Key库。**当前SnapshotResolver.resolve及DeveloperProfileResolver只允许translation capability**，并未接通qa/embedding。

06应明确QA请求的个人/默认模型选择、用户授权、输入外发提示和费用边界，再与04扩展请求级解析器或专用QA profile快照。不能伪称translation能力来绕过协议，也不能将用户密钥塞进全局ADAPTERS。读取本人已验证修订、模型请求后复核修订、取消/限流/超时、失败不回退的规则继续沿用。embedding若需不同模型属于另行能力设计，本轮未实现。

## 文件分工与联调矩阵

- 06：其自己的问答服务/存储、AnswerResolver生产适配器、权威证据校验、前端保存事件和失效错误；不要直接写notes表。
- 05：其自己的版本化提取/chunk读取、Document解析状态、旧版本生命周期；不要改写笔记来源块。
- 04：当前answer_sources/note_captures、SaveToNoteDialog/AiAnswerNoteBlock/notes.captures已就绪；确认真实DTO后只做最小适配，不重写搜索/翻译/高亮。
- 公共冲突热点：backend/app/models.py、main.py、documents.py、frontend/src/views/ReaderPage.vue、reader/context.ts/navigation.ts、docs/design/api-contracts.md及迁移编号。保留已验收参数和消费者；新API不得假定旧单文献NoteDraft仍是存储协议。

最终双方在临时SQLite先接真实解析器，测试：稳定回答新/当前/其他笔记、不可变版本/重复/CAS/草稿、两用户同PDF隔离、错误文献/伪quote/坏页码/过期/删除恢复、none确认、服务故障不能绕过。然后只用双方授权个人模型及少量公开合成PDF做真实问答→证据→保存→搜索→来源页导航；记录供应商/模型/HTTP及证据绑定，不能以Mock代替。真实MySQL随后单独在litera_test或新实例验收。

未确认事项：06的实际接口/ID格式/修订和撤销语义、05的版本化证据读取、模型capability及预算、下一个迁移编号、服务部署顺序。本轮没有向组员发消息或改动05/06实现。
