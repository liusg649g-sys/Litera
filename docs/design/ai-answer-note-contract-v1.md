# AI 问答结果保存笔记：集成接口契约 v1

**状态：总体设计方向已获用户认可；P3-D1 已实现并人工验收通过，统一5183亦已验收。Change06真实接口与字段仍待负责人确认，本文的拟新增QA接口不代表已存在或已承诺。**
记录时间：2026-10-26，北京时间。项目：`<项目目录>`。
分支：`local/litera-dev-20261020`；HEAD：`947dc3cc6381ce4b19d587762950f381b6e31100`。

## 1. 当前实现核对：哪些能复用，哪些还不存在

依据：上级收尾报告 `LITERA_TRANSLATION_NOTES_REVIEW_20261026.md`、统一交接第47节、Change04/06 proposal/design/spec/tasks、P3-B开发记录及下表源码。本轮只检查当前工作区，未fetch或检查其他成员未提交分支；其外部进展须由对方确认。

| 能力 | 当前状态/代码依据 | 本契约的处理 |
|---|---|---|
| 问答生成、回答读取与稳定answerId | **本地仅规划**：Change06任务全部未勾选；`docs/design/api-contracts.md:278`的AnswerDTO只有目标定义；main.py未注册QA路由，models.py及0001–0007无qa_answers实体/迁移 | 由06提供，不能假定现有GET回答接口可调用 |
| 检索、版本化chunk、引用验证 | **本地仅规划**：Change05/06约定extractionVersion/chunk/page/quote；未发现可供笔记调用的实际回答/证据服务 | 05供版本化证据，06提供可验证的回答快照；笔记不实现RAG |
| 通用模型调用 | **已实现的共享基础设施**：`backend/app/ai_service.py`、`model_service.py`供当前翻译使用 | 有模型适配器不等于QA模块已实现；笔记保存不调用模型、不读Key |
| 笔记CRUD、M:N、CAS与草稿 | **已实现/已验收**：`notes.py:create_note_router`、`models.py:Note/NoteDocument`、`frontend/src/notes.ts` | 复用，禁止另建笔记本体或单文献notes.document_id |
| 原文/译文来源保存 | **已实现/已验收**：`note_captures.py:79/121/161/219/246`，POST `/api/v1/notes/captures`、GET `/notes/capture-config` | 复用保存外壳、事务、幂等、限额；新增独立AI分支 |
| 新建/当前/其他笔记目标 | **已实现**：`SaveToNoteDialog.vue`，`NotesPanel.vue:82` prepareForInsert/afterCapture | 保留三类目标，扩展AI预览和确认文案 |
| AI保存来源类型 | **尚未实现**：CaptureSource/storedSourceBlock只支持pdf_excerpt、translation_excerpt；旧NoteDraft中的ai只是类型 | 新增ai_answer判别分支，不能将答案塞进originalText伪装PDF原文 |
| 来源页跳转、B1高亮 | **已实现/已验收**：navigation.ts、sourceHighlight.ts、PdfPage.vue、ReaderPage.vue | AI引用先复用可靠页跳转；chunk不是PDF.js textRanges，不伪造精确高亮 |
| 个人笔记搜索 | **已实现/已验收**：notes.py::_search_note、notes.ts、NotesPanel | 原字段保持；新增AI问题/回答及引用原文命中 |

P2/P3核心已验收，既有规约和README中的历史“尚未实现”描述不代表这些代码缺失。本轮不改其任务勾选，也不改业务源码。

## 2. 推荐边界：浏览器传回答引用，服务端取权威快照

推荐同一FastAPI应用内的服务调用，不在笔记服务里重复HTTP请求或生成回答：

```text
问答前端 → 06生成并发布不可变回答 → 显示回答
         → 点击保存，冻结该回答ID/修订和预览
         → 04现有目标对话框（先flush草稿）
         → POST /notes/captures（AI来源分支）
         → 服务端resolve_answer(认证用户, ID, 修订)
         → 校验回答/文献/引用 → 原子保存笔记块与显式关联
         → 返回NoteDTO，既有控制器安全接收并显示成功
```

**拟新增06内部接口：**
`resolve_answer(principal_id, answer_id, answer_revision) -> ResolvedAnswerV1`。
同进程传入已认证principal，内部检查owner；业务层不信任浏览器的ownerId或“verified”标签。

**拟新增06受保护读取接口：**
`GET /api/v1/qa/answers/{answerId}?revision=N`，返回下面的公开快照。
这是建议路径，现不存在；可与06实际路由协商，但其鉴权和字段语义不可省略。
原 `POST /api/v1/documents/{id}/qa`同样是规划接口；由06实现，返回同一快照形状。

推荐06持久化回答及其不可变引用快照，避免依赖浏览器内存或短暂模型回执。重试保存不重新提问，不产生新的模型费用。若06选择其他可信存储，仍须满足相同读取、归属与不可变约束；不得临时用客户端JSON代替服务端来源。

## 3. 06需要提供的数据：ResolvedAnswerV1（拟新增）

| 字段 | 约束/用途 |
|---|---|
| schemaVersion | 固定1，指本契约的回答形状，不是note.version |
| answerId、answerRevision | answerId为服务端UUID；revision为正整数。已发布的同一ID+revision内容不可变；重新生成答案推荐新ID，不能覆盖已有快照 |
| documentId、documentTitle、fileSha256 | 06从本人有效文献/附件派生；64位SHA标识PDF版本，标题只用于展示，不决定来源 |
| mode、question、answer | mode=question/summary/analysis；question模式必须有非空原始问题，其余可null；answer为完整生成文本，不混入引用原文 |
| status | answered或insufficient_evidence；处理/失败中的请求不发布为可保存答案 |
| contextRevision、createdAt、expiresAt | 保留生成时上下文；expiresAt可null。contextRevision只是前端防竞态值，不是身份凭证、文件版本或note.version |
| extractionVersion | 实际引用的提取版本；若尚无可靠提取且属证据不足响应，可null，不能填最新版本冒充 |
| provenance | 服务端派生model_api或isolated_mock；Mock必须醒目标记，生产者不能接受客户端决定该字段 |
| evidenceState | 服务端派生verified或none；指引用文字/归属的验证状态，**不代表AI推论真实正确** |
| citations[] | 每项含稳定citationId（该回答内唯一）、documentId、extractionVersion、chunkId、pageNumber、quote、fileSha256；页码为1-based物理页，quote来自服务端证据而非模型自报页码 |
| 内部owner_user_id | 仅服务端解析使用，不允许客户端指定，不必返回浏览器 |

建议首版上限：问题6000字符、回答20000字符、引用最多20条/每条quote最多6000字符；超限明确422，不截断后声称完整保存。与06实际生成限制共同确认。note标题200、每note最多100块、sources总计1MiB继续复用P3-B限制，不抬高既有限额。

### 引用可信与无引用：两条明确路径

- `answered + evidenceState=verified`：至少1条引用；全部同owner、同原始documentId、同PDF哈希/实际提取版本。chunk属于该版本页面，quote可在该版本页文本核对。首版不做跨文献问答；笔记可关联多文献，不扩大QA检索范围。
- `insufficient_evidence + evidenceState=none`：citations必须为空；允许用户明确确认后保存“问题+AI生成内容/无法确认说明”，显示“未核实AI回答，无可靠原文引用”，不填页码，不显示查看原文按钮。所关联的文献只是**提问上下文**，不是该回答的证据。
- 有引用却校验失败（伪chunk/错页/错quote/越权/文件变更），或证据服务未就绪，**不得剥掉错误引用后悄悄转为none**。拒绝本次保存并保留预览；需要06重新发布合法回答。
- 引用核验只证明quote对应那份PDF/版本/页面，不能宣称AI答案的每一句已被证实。界面将“AI回答”和“已核验PDF引用”分区展示，均作为安全纯文本。

## 4. 04保存API与来源块（拟增量扩展）

### 4.1 请求：复用POST /api/v1/notes/captures

现有PDF/翻译请求保持原样；source新增按kind判别的AI分支。**AI请求不携带question、answer、quote、pageNumber、owner、provenance或verified值**，这些只能由resolver提供。

```json
{
  "operationId": "11111111-1111-4111-8111-111111111111",
  "noteId": "22222222-2222-4222-8222-222222222222",
  "version": null,
  "newNoteTitle": "AI 阅读笔记",
  "associationMode": "link",
  "source": {
    "kind": "ai_answer",
    "answerId": "33333333-3333-4333-8333-333333333333",
    "answerRevision": 1,
    "historical": false,
    "confirmHistorical": false,
    "confirmUncited": false
  }
}
```

以上为合成示例，不是当前可执行请求。
新笔记沿用version=null、newNoteTitle非空、固定新noteId；已有/当前笔记沿用newNoteTitle=null、version为最新目标note修订。已有笔记追加不修改标题或个人正文。

- 若目标尚未关联回答的原始文献，明确选择link（新增这一条关联）或keep（不新增）；当前阅读标签和笔记其他关系不作为来源。
- 新笔记确认界面明确展示将关联的原始文献；取消即无写入。现有笔记即使在B中编辑，保存A的回答仍只能标为A。
- confirmUncited仅用于合法none回答的知情确认；不能覆盖来源错误。history标记是UI保存意图，不是权限或证据；旧结果须明确确认，服务端仍独立校验真实来源。
- AI引用不经过PDF摘录的“把全部answer与原页匹配”规则；它用新的回答/引用验证器。现有pdf_excerpt/translation_excerpt校验不降低、不绕过。

### 4.2 响应、能力和错误

沿用 `{note,blockId,created,linked,replayed}`：首次成功201，同operationId同意图重放200。新增可选 `deduplicated:true` 表示另一operationId已将同一answerId+revision保存到同一note；返回原blockId，不再追加。旧消费者只检查现有字段仍兼容。

拟扩展现有capture-config，保持formatVersion=1及所有旧字段，增加：
`supportedSourceKinds` 和 `aiAnswerCapture:{available,reasonCode?}`。
只有AI分支和resolver确已接通才声明可用；未接入显示“AI回答保存尚未接入”，不靠notes表存在就启用按钮。某篇文献索引未就绪另按06状态提示。

| 状态 | 拟新增/沿用错误语义 |
|---|---|
| 401/403 | 未登录/Origin或CSRF不符，沿用现有包络 |
| 404 | 笔记、回答或文献不存在/越权，统一不可访问，不泄露他人记录 |
| 409 | note.version冲突、operationId意图冲突、answerRevision或PDF版本不一致、引用版本不能核对；不自动换版本继续保存 |
| 410 | 回答已撤销或过期（若06有该生命周期）；本次新保存被拒绝 |
| 422 | 输入/大小不合法、引用不匹配、无引用未确认；不创建半条笔记 |
| 503 | NOTES_NOT_READY或AI回答/证据服务未就绪；不得把不可验证当合法无引用 |
固定安全错误码/中文提示沿用现有error包络；不返回堆栈、原始上游错误或Key。具体新增code名称在实施前与06统一。

### 4.3 保存后的AI块

继续写notes.sources，不把生成答案重复追加到notes.content。建议AI分支结构：

```text
{
 id: operationId, kind: "ai_answer", blockSchemaVersion: 1, createdAt,
 question: string|null, answer: string,
 answerRef: {answerId, answerRevision, mode, status, provenance},
 contextDocument: {documentId, title, fileSha256, contextRevision, extractionVersion},
 evidenceState: "verified"|"none",
 citations: [{citationId, documentId, fileSha256, extractionVersion,
              chunkId, pageNumber, quote}],
 historical: boolean, uncitedAcknowledged: boolean,
 requestFingerprint: 服务端保存意图指纹
}
```

contextDocument与citations区分提问文献和证据。none块citations=[]，无伪造的pageNumber=1/0；不把AI回答当成originalText。不另建note实体或复制整条笔记。

保持note级source_schema_version=1和旧块字节/含义；仅增加可识别kind及blockSchemaVersion。现有前端会把未知kind计为“无法识别的来源”，不删除它，但不能据此宣称旧UI已支持AI显示。新旧读写器兼容测试通过前不得上线；如实际证明必须改变note级版本，先另行报兼容/迁移方案，不把全部旧note强制改成2。

## 5. 权限、幂等、过期与草稿规则

1. **权威来源**：先用session用户解析回答及目标笔记归属；读取本人有效源文献/附件并核对保存哈希。citation的owner、doc、版本、chunk、页和quote由06/05服务核验，客户端传同名字段应被schema拒绝。保存不触发模型或检索重算。
2. **版本与过期**：重新提取但旧版本仍保留且文件哈希一致时，可核对旧引用并保存其旧版本；不能悄悄改为当前版本。版本已丢失、文件变化、回答撤销/过期则阻止新保存；不能用“无引用确认”绕过。已存笔记快照不因原回答到期被删除。
3. **关联独立**：M:N关联仅按用户选择增量link/keep。解除A关联或永久删A不删已存AI块；来源快照仍是A。源PDF失效时保留文字，导航明确不可用，绝不改为当前B。
4. **一次保存意图幂等**：冻结operationId、目标noteId、answerId/revision、标题、关联方式及确认选择；指纹不含预期note.version，其他意图变化不能沿用旧ID。未知网络结果只重试同一意图，不先生成新笔记。提交响应丢失后的重放先检查owner及已存块，再返回已有结果；即使后来源回答到期/解绑，也不重复插入、重新关联或重验成另一个回答。
5. **防重复与锁**：同一note+answerId+revision默认只保存一次，不同note可各存。锁内复核重复块并使用既有CAS；并发不同operationId也不能双插入。重复返回不补建已被解除的关系；需要关联时走独立显式关联操作。锁顺序沿用源文献→目标note，06协调回答生命周期的锁/快照规则；慢证据读取在锁前完成，写入前复核未撤销/未换文件，避免长事务等模型。
6. **前端竞态**：问答生成的requestId/epoch及documentId/contextRevision过滤迟到结果；点击某条结果时冻结它自己的ID、修订和来源。换PDF/账号关闭待存对话框，旧响应不更新新账号/新目标。明确历史保存操作仍使用旧回答自己的来源，不把它标为当前问答；账号退出清理UI状态。
7. **自动保存**：打开目标对话框前调用NotesPanel.prepareForInsert/flush。提交前确认当前目标无未保存编辑并获取目标version；保存中冻结目标。409保留草稿/回答和选择，显式重读后再确认，不能自动采用服务器新version覆盖。成功仅经afterCapture/acceptCapture接收，不能让旧DTO覆盖用户其后新输入。
8. **无引用与失效区别**：只有服务端合法发布的none回答，经勾选“保存未核实AI内容，不包含可靠引用”才能保存；UI不是成功证据。回答存在但证据服务故障、错误引用或权限失败仍拒绝。
9. **来源导航**：可信citation逐条展示“原始标题 · PDF第X页”，只使用各自documentId/SHA/page复用C2-A。chunk偏移不转成PDF.js textRanges，不给AI块自动显示B1精确高亮。引用版本后续不可再核验时明确标记；同一PDF哈希仍能可靠页跳转时只能报告页级定位，不假装新版本文字核验通过。PDF哈希变化/删除/无权限则拒绝跳转。
10. **安全呈现/搜索**：问题、回答与quote都按文本显示，不执行HTML或模型指令。搜索增量支持ai_question、ai_answer，可信quote沿用source_original；无引用的命中不填pageNumber。保留中文/英文、去重、分页、长度上限和草稿隔离。

## 6. 对接组件与团队分工

| 责任方 | 需要提供/增加的能力 | 不应越界的事项 |
|---|---|---|
| 06问答负责人 | 发布/持久化不可变Answer快照及稳定ID；resolve/read回答；owner/有效文献/引用验证、撤销/过期、Mock标记；问答结果“保存到笔记”事件 | 不直接写notes表，不用模型自报页码作证据 |
| 05提取负责人 | 可按documentId+fileHash+extractionVersion读取的页/chunk证据；旧版本保留/失效策略 | 不把新提取版本无声替换旧引用 |
| 04笔记负责人（本模块） | CaptureInput/source判别联合、AI验证器调用和块构造；复用保存事务/CAS；AI卡片/搜索/能力字段；对话框三目标与确认文案 | 不实现检索/模型/问答生成，不访问真实Key |
| 02阅读器接口协调 | 复用ReaderPage.openCapture/captured、NotesPanel.openSource和navigateReader；AI引用走已验证页码路径 | 保留P2/P3及B1，未经可靠PDF.js范围不做AI精确高亮 |
| 双方共同 | DTO/error/生命周期/锁顺序契约样例、临时SQLite真实HTTP联调、实际问答与引用验收 | Mock通过不能宣布真实问答联调成功 |

具体受影响生产者/消费者（**未来实施清单，本轮未改**）：
- 后端：06新回答服务；`backend/app/note_captures.py`的CaptureInput/checked_sources/existing_capture/make_block/add_capture_routes；`notes.py::_search_note`。
- 前端：06问答面板发出保存意图；`notes/captures.ts`判别联合；`SaveToNoteDialog.vue`目前强制原文/页码的预览和校验须按kind分支；`NoteSourceBlocks.vue`区分AI与PDF/翻译；`notes.ts`扩展搜索字段；ReaderPage/NotesPanel继续复用草稿接入。
- 旧NoteDTO以`frontend/src/notes.ts`的独立本体+documents+sources为真源；不要依照旧文档`NoteDTO extends NoteDraft`单文献模型重写接口。TranslationProof继续仅属于翻译分支，不把它当AI回答证明。

## 7. 数据库与发布风险

**笔记侧预计无需新表/列/迁移**：0007已有JSON来源及共享CAS版本，AI块为加法结构；不得改已应用0007或回填旧来源。仍需临时SQLite兼容测试和后续真实MySQL JSON/事务验证，不能以离线DDL代替。

06的稳定回答持久化及05/06页/chunk/index实体目前未存在，可能需要其负责人新迁移；这是独立依赖，不是“整个集成零迁移”。迁移编号、Alembic head与团队其他新迁移必须协调，不在本轮预定0008或执行迁移。

将来加载5180前先审查实际head/维护副作用、按既有方式停机联合备份数据库与PDF/资产、核验哈希与SQLite完整性。若06新迁移影响现有预览启动器head检查，不得绕过或降阈值；另行审核兼容方式或新隔离实例。5177及业务MySQL不获授权不得迁移。失败保现场，回退应用/禁AI入口，不删表、不覆盖备份。

本轮仅写契约/交接文档，没有触碰任何数据库、启动器或运行服务。

## 8. 最小可独立开发阶段（均待审核后授权）

| 阶段 | 交付/依赖 | 验收界限 |
|---|---|---|
| S0 契约确认（本轮） | 本文与双方确认项；不修改业务实现 | 用户和06确认字段/路由/来源状态/删除语义；不声称已集成 |
| S1 笔记侧隔离适配 | 注入FakeAnswerResolver，仅APP_ENV=test的显式夹具；临时SQLite真实保存、AI卡片和三目标、搜索/草稿/幂等 | 标明isolated_mock；真实HTTP/数据库写入只在临时环境，不能宣称真实问答或模型通过 |
| S2 06真实来源服务对接 | 06/05实际回答读取、引用和文件版本服务就绪；替换resolver，保持笔记接口不变 | 不使用客户端伪造引用；真正生成/读取答案→验证→保存的联调证据；若生成模型仍Mock必须明确 |
| S3 安全加载与联合人工验收 | 回归通过、预览备份/版本审查；5180继续隔离策略，真实模型另用后续明确批准环境 | 用户检查新/已有/当前保存、无引用标记、来源/刷新/跳页和P2/P3不回归；少量真实QA+检索验证后才称完整端到端 |

06未就绪时可独立做S1并稳定其不可用提示，不能以FakeResolver取代课程最终集成。用户自定义模型、页面旋转、跨物理页摘录和OCR都不在这些阶段内。

## 9. 测试与人工验收标准（计划，尚未执行）

| 层级/场景 | 必须观察的结果 |
|---|---|
| 契约单测 | 回答ID/修订不可变；question模式非空；多引用同文献/版本；none无页码；错误引用不自动降级；未知/超长字段拒绝；无模型/密钥调用 |
| 临时SQLite/API | 新笔记+块+link原子成功；现有笔记CAS追加且正文不变；keep不改关系；同/不同operationId并发重复只1块；响应丢失重试200，之后解除关系重放不重建 |
| 权限/真实性 | 未登录401；他人note/answer/doc/chunk拒绝且不泄露；CSRF错误拒绝；篡改question/answer/quote/page/verified不能写；SHA/revision不一致、过期/撤销、失效提取版本明确失败 |
| 无引用/不足/依赖 | none未确认不可保存；确认后卡片明确AI未核实、无引用按钮/页码；索引/证据服务503不能伪装none成功；不发二次模型请求 |
| 前端/异步 | 新/当前/其他目标可切换；历史结果须确认；换PDF/账号、连续提问、迟到返回不串源；pending保存目标冻结；800ms草稿flush，离线/409输入保留，保存后不被旧DTO覆盖 |
| 数据/搜索/导航 | 刷新重登AI块及来源不变；AI问题/答案/quote可搜且用户隔离无重复；关联A/B、解除A后块仍为A；失效PDF有提示；每条有效引用跳原PDF页，不错误出现B1高亮 |
| 兼容回归 | PDF/翻译captures原请求和错误不变；当前/历史译文、24小时回执、安全文字映射保持；CRUD/自动保存/搜索/标签/批注/C2-A/B1照常；混合来源及未知kind读取不丢内容 |
| 存储/发布 | 旧0007库/旧空与混合来源无需回填；SQLite JSON/CAS验证；真实MySQL事务另列实际结果；业务库未批准不迁移 |
| 真实联合验收 | 06真实问答+检索产生一条普通问题答案，人工对照引用PDF页；保存新/当前/其他笔记并重登；单独记录模型来源和HTTP结果，Mock/真实模型/数据库测试分层，不拿健康200替代 |

人工验收只用独立测试账号、合成或明确允许的PDF：先检查回答/引用分区和原文页，依次保存新笔记、当前笔记、其他已有笔记；核对关系和正文不变；再检查none确认、历史结果、刷新/重登、逐条跳页；最后在专用临时笔记上测试断网/冲突/删除来源，不能用已有私人数据做破坏性用例。

### 需其他成员配合确认

1. 06是否有尚未提交的实际实现？提供真实路由、DTO、回答存储和引用服务，不只给tasks勾选。
2. 接受稳定answerId+不可变revision与服务端resolve接口吗？回答保留时长、撤销/过期以及旧提取版本策略是什么？
3. 接受none回答需明确确认、无证据页码/导航的产品规则吗？summary/analysis的question=null是否匹配其实现？
4. 接受首版只引用同一PDF、多引用逐项页级导航、不混用chunk和PDF.js范围吗？
5. 双方确认错误码、限额、Mock标识、并发锁顺序，以及不同operationId同answer去重后不自动重关联的行为。
6. 06/05迁移与分支何时可安全集成？哪个负责人提供独立测试实例和真实检索/模型验收证据？

本轮没有执行上述测试或启动S1。完成用户/团队审核前，本文是可评审方案，不是已上线接口承诺。

## D1 实现映射（2026-10-26，非真实问答联调）

- 笔记内部协议：`backend/app/answer_sources.py` 的 `AnswerResolver.resolve(db, owner, answer_id, revision)` / `verify_citation(...)`；D1采用请求级依赖注入，默认不可用，不生成或持久化问答。
- 笔记侧预览：`GET /api/v1/notes/answer-preview/{answerId}?revision=N`，仅作为04保存前的权威预览；并未实现本文拟议的06 `/qa/answers`。
- 保存复用`POST /api/v1/notes/captures`，AI请求仅有ID/修订/确认标志，服务端独立核对PDF实际SHA256、归属、页码与原文。`verify_citation`还须由实际适配器核对05/06版本化证据绑定，不能以“PDF中存在同句”代替真实问答引用证明。
- `notes.sources`追加`ai_answer`块，不改0007及source_schema_version；旧类型继续读取。AI生成文字与引用分开；AI引用没有PDF.js选区，复用页码导航，不宣称精确高亮。
- 当前只支持单文献回答引用。多文献QA引用、可空问题/摘要的完整语义、回答有效期/修订失效规则、解析版本与chunk绑定及正式服务错误映射，须与负责人共同确认后进入D2。
- 固定Mock仅由`notes_preview.py`与`note_captures_e2e_server.py`显式启用，双重路径/APP_ENV/空模型配置约束；普通应用不注册Mock列表/合成PDF下载路由。合成PDF测试须用户主动上传，不在启动时增改账号、文献或问答。
- 具体结果见`docs/development/p3-d1-ai-answer-notes.md`与统一交接第49节；Mock与临时SQLite成功不等于真实QA、MySQL或用户验收通过。


## GitHub交付协调补充（2026-10-26）

当前代码已存在AnswerResolver/ResolvedAnswer/AnswerCitation、受保护answer-preview和captures的ai_answer分支；上文“未来笔记侧修改清单”为契约初稿历史，不能据此重复开发。06真实解析器/问答接口仍未存在。本轮协调字段、单文献限制、共享个人模型能力边界及双方联调矩阵见[团队集成协调](../delivery/team-integration.md)。不把固定Mock记录或伪引用当真实服务。
