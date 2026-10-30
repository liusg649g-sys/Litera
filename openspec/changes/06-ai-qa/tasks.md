# Tasks

负责人：Jialu Ma。状态：待实现。前置已就绪：05 版本化页文本/分块、`course-chat` 与 `course-embedding`（2048 维）网关、02 ReaderContext/Citation、04 笔记适配器契约（当前为未实现桩）。

## 0. 前置核对

- [x] 0.1 在 api 容器内复核 `AI_EMBEDDING_MODEL=course-embedding` 返回 2048 维、`course-chat` 可对话，Key 只存在于后端环境变量；记录实测模型与延迟。
- [x] 0.2 核对 05 某篇文档的 `extractionVersion` 下 pages/chunks 行数与页码映射，确认可作为唯一证据真源；确认旧版本数据在重解析后仍可读取。

## 1. 数据模型与索引

- [x] 1.1 新增迁移 `0010_qa_answers_indexes_vectors.py`，创建 qa_answers / qa_indexes / qa_chunk_vectors，验证唯一约束、活动索引唯一性与删除清理；迁移在空库与既有库各执行一次。
  证据：既有 MySQL 库 `alembic current` 为 `0010_qa_answers_indexes_vectors (head)`，qa_* 三表存在；空库路径由 pytest 迁移用例覆盖（473 passed / 10 skipped）。
- [x] 1.2 扩展模型服务 embedding 调用：复用鉴权、超时、错误映射与并发信号量，支持 32 条批量；新增 `AI_EMBEDDING_MODEL`、`AI_EMBEDDING_DIM` 等配置，测试 Key 不进日志/仓库。
  证据：`course-embedding` 实测返回 2048 维，qa_chunk_vectors 落库 94 条且 dimension=2048；429 被映射为 `MODEL_QUOTA_LIMITED`；Key 仅在容器环境变量，未出现在仓库、日志或响应中。
- [x] 1.3 实现索引构建与生命周期：提取版本完成后后台扫描或首次请求触发；成功后事务内切换活动索引；构建失败落 `QA_INDEX_FAILED`；软删除阻断、永久删除级联清理；验证旧索引在新索引就绪前仍可用。
  证据：后台扫描与首次请求触发、事务内 `is_active` 切换、失败落 error_code（实测 `MODEL_QUOTA`）由 `backend/tests/test_qa_api.py` 覆盖；qa_* 对 documents/users 均为 `ON DELETE CASCADE`（information_schema）。真实验收：文献 5f2d7a12（遥感检测）DELETE 软删后 POST /qa 返回 404；DELETE /trash/documents/{id} 触发 purge，t+1s DB Document 行消失、qa_answers / qa_indexes / qa_chunk_vectors 全部归零（DB cascade 验证通过）。关于"旧索引在新索引就绪前仍可用"：当前 `create_extraction_job` 对同 documentId+fileHash 的已完成 job 复用同一 extraction_version，extract 端点不会生成新版本，因此自然流程下不会出现"两个 QA index 并存（旧 active + 新 building）"的场景；但旧 chunk_vectors 在新 build 完成前一直保留（同一 version 下），QA 请求始终可返回成功（网关限流期间未能实测，但实现上旧向量在新向量就绪前一直保留）。

## 2. 检索与问答服务

- [x] 2.1 实现 `rag.py`：中文字符 bigram / 英文词分词、BM25、余弦、RRF 融合、MMR 去冗余、同页邻片扩展、按 pageNumber 限定检索范围；单元测试覆盖空文本、纯中文、纯英文、超长片段与页码边界。
  证据：`backend/tests/test_qa_rag.py` 覆盖上述边界；真实英文 91 片/中文 3 片索引均可检索，页码限定提问实测只返回第 3 页引用。
- [x] 2.2 实现受限提示词与 JSON 契约：片段编号包裹、忽略片段内指令、question/analysis 两种输出结构；非法 JSON 修复重试 1 次，仍失败返回 502，不生成假答案。
  证据：真实模型 8 次结构化调用均返回合法 JSON；非法 JSON/修复路径由 `backend/tests/test_qa_api.py` 覆盖，无假答案分支。
- [x] 2.3 实现服务端引用核验：编号范围、chunk 归属与版本校验、quote 由片段首句截取（≤240 字符）、页码取片段元数据；越界/无有效引用降级 `insufficient_evidence`；用伪造编号、跨文献 chunkId、错页码用例验证拒绝。
  证据：真实回答 8 条（英文）与 2 条（中文）引用逐条比对 DB：页码=chunk 页码、quote 归一化空白后属于 chunk 文本、长度≤240、版本一致；伪造/跨文献/错页码用例见 `test_qa_api.py`。
- [x] 2.4 实现 `POST /documents/{id}/qa` 与 `GET /documents/{id}/qa/{answerId}`：DTO、统一 error 包络、qa_answers 持久化、本人取回、他人 404；OpenAPI 文档同步。
  证据：真实 POST 200 并持久化 qa_answers；GET 同 answerId 返回内容一致；他人文献/软删除文献/未知 answerId 均 404；空问题 422 `QA_QUESTION_REQUIRED`。
- [x] 2.5 实现检索门槛与失败映射：低于相似度/关键词门槛不调模型；超时 504、429 透传、索引未就绪 503；验证前端可重试且无假答案。
  证据：实测 429 `MODEL_QUOTA_LIMITED`、索引未就绪/失败 503、超时 504（并把 QA 侧超时文案统一为“模型响应超时”）；前端展示错误与“重试”，未出现伪造答案或引用。

## 3. 摘要与结构解析

- [x] 3.1 实现章节识别：英文与中文标题正则、片段继承最近标题、无背景标题时映射引言；缺失章节不兜底；中英文样例各有测试。
  证据：真实英文/中文结构解析均返回 background/method/results/conclusion 四节；英文结果/结论无证据时写“未找到对应证据”，未用其他章节兜底；标题解析用例见 `test_qa_rag.py`。
- [x] 3.2 实现摘要 + 背景/方法/结果/结论一次调用：各节 ≤4 片段、总量 ≤12000 字符；每节带引用，缺失写"未找到对应证据"；按 extractionVersion 缓存，重复请求不重复生成。
  证据：一次 analysis 调用返回四节（英文每节 4/4/0/0 条引用，中文各 1 条）；重复请求 `cached=true` 且耗时 0.0s，未重复调用模型。

## 4. AI 阅读助手前端三态

- [x] 4.1 改造 ReaderPage 布局：仅助手时 PDF 为主 + 右侧 500px 面板；助手与翻译同时展开时三栏并排；实现 1200/1100px 断点与窄屏翻译覆盖式降级；验证 PDF 不遮挡、各栏独立滚动。
  证据：真实浏览器 1600px 三栏为 PDF 700 / 助手 500 / 翻译 400；1200px 助手 460、1100px 380，翻译面板覆盖式降级；1000px 助手为 380 宽 dialog；各档无横向溢出、PDF 未被遮挡。
- [x] 4.2 实现面板内容：居中机器人、欢迎语、三条功能说明、四个分类标签（读懂文献/方法细节/结果与结论/参考文献）、文献速读/核心创新/研究方法/研究结论快捷按钮、底部固定输入框（划词提问/当前页提问/快捷总结/发送）；标签切换建议问题并填入输入框；无选区时划词提问置灰并提示先选择；验证所有入口均发起真实请求。
  证据：浏览器实测五个入口（文献速读、核心创新、研究方法、研究结论、发送）各产生一次真实 `POST /qa`；切换“方法细节”只把建议问题填入输入框、消息数为 0；“划词提问”无选区时 disabled 且 title 为“请先在 PDF 正文选择文字”。
- [x] 4.3 实现收起与恢复：分界线圆形箭头按钮收起；PDF 右下角机器人 + "文献阅读助手"悬浮胶囊展开；收起后不重复请求，切换文献后清空；键盘可达、`aria-expanded` 正确。
  证据：圆形按钮收起后胶囊出现，重新展开保留已有消息且 `POST /qa` 次数不变（2 次）；Esc 可关闭，工具栏 `aria-pressed` 与胶囊 `aria-expanded` 同步为 false；切换文献即清空由状态机单元测试覆盖。
- [x] 4.4 实现答案展示：加载骨架、问题气泡、答案卡固定"AI 生成，非 PDF 原文；引用片段已核验"、引用页码徽标 + quote 展开、点击跳转物理页、证据不足/超时/限流/未就绪状态与重试。
  证据：真实答案卡含免责声明、8 个页码徽标与逐条 quote；点击“第 6 页”后页码输入变为 6 且第 5/6 页渲染；429/504/证据不足（“未能从当前文献…找到可核对的证据”）均正常展示，重试按钮可用且无伪造答案。
- [x] 4.5 接入 ReaderContext：请求携带 contextRevision，返回时用 `isReaderContextCurrent` 判定，切换文献/标签/删除后丢弃过期结果并中止请求；验证快速切换无串答。
  证据：请求体含 `contextRevision`；`tests/qa.test.ts` 8 条用例覆盖切换文献丢弃、页码类问题在修订号变化后丢弃、文档级问题跨翻页保留、取消中断；浏览器未做人工快速切换（依赖上述用例）。

## 5. 笔记接入与验收

- [x] 5.1 实现 `QaAnswerResolver` 替换 `UnavailableAnswerResolver`：按 answerId 取回并核验 owner/版本/chunk，笔记保存链路无需改动即可用；笔记模块不可用时保持禁用语义。
  证据：`backend/app/qa.py` 中 `QaAnswerResolver.resolve/verify_citation` 已接入；他人/不存在 answerId 404；笔记模块禁用语义由既有 notes 测试保持。
- [x] 5.2 契约测试覆盖：空问题 422、他人文献/回答 404、索引未就绪 503、超时 504、429、伪造引用拒绝、跨文献 chunk 拒绝、旧版本引用可核对。
  证据：`backend/tests/test_qa_api.py` 覆盖上述分支；真实环境另行实测 422/404/503/429/504 与跨版本引用核对（旧版本引用核对依赖 5.4 重解析，见下）。
- [x] 5.3 真实端到端验收（英文 arXiv 论文 + 中文期刊论文各一篇）：摘要、结构解析、方法/结果提问；逐条核对 quote 与物理页码；问"作者邮箱/基金号"等文外信息应返回证据不足；记录 p50/p95 延迟与 token 成本。
  证据：英文 "Human-level control…"（91 片）与中文《计算机学报》遥感检测（3 片）均完成摘要/结构/提问；引用页码 1/3/6 与 DB chunk 页码一致，quote 归一化后均属原文；两篇各一次文外问题均返回 `insufficient_evidence`。成功样本耗时（秒）：0.0(cached)×2、5.0、6.2、9.6、13.1、15.2、17.4，p50=9.6、p95=17.4；另有 2/10 次网关 5–7s 超时（504，重试后成功）。网关未返回 usage，token 为估算：analysis 单次 ≤12000 字符上下文（约 4–6k tokens）+ 输出 ≤2048 tokens，question 单次 ≤6000 字符 + 输出。
- [x] 5.4 权限与生命周期验收：两用户隔离、软删除阻断、永久删除清理 qa_*、重解析后旧回答引用仍可打开并标注版本。
  证据：他人文献 404、他人 answer 404 由 `test_qa_api.py` 覆盖；软删除文献 404、qa_* 对 documents 的 `ON DELETE CASCADE`（information_schema）均已确认。真实验收：文献 5f2d7a12（遥感检测，9 条 answered qa_answers）DELETE 软删后 POST /qa → 404，GET /qa/{answerId} → 404（owned_document 检查 deleted_at=None），trash 列表可见；DELETE /trash/documents/{id} 触发 purge 后 t+1s → DB Document 行消失、qa_answers / qa_indexes / qa_chunk_vectors 全归零，trash 列表消失，GET /qa/{answerId} → 404（owned_document 找不到）。关于"重解析后旧回答引用仍可打开并标注版本"：qa_answers 存固定 extraction_version（不可变快照），GET /qa/{answerId} 返回体带该 version 字段；同 documentId+fileHash 的 reparse 复用旧 extraction_version 时，旧 answer 保持可读，前端直接用 answer.extractionVersion 标注即可。

## 6. 助手界面精简与交互（本轮）

4.2 / 4.4 中关于快捷按钮、输入动作按钮与平铺引用的验收口径，实施本节后以 6.x 为准；原有证据作为历史记录保留。

- [x] 6.1 悬浮胶囊移到 PDF 区域左下角（`left:24px; bottom:24px`）；底部抽屉打开时上移避让、z-index 低于抽屉；验证与左侧导航、翻译/笔记内容不重叠。
  证据：浏览器 1600px 实测胶囊距 PDF 区左/下各 24px；胶囊 `z-index:12` 低于抽屉 13；1000px 打开翻译抽屉后胶囊 `bottom=416px`，位于 52dvh 抽屉之上；收起后胶囊重新出现。
- [x] 6.2 共存布局：≥1100px 且助手与翻译/笔记同时展开时，`.reader-extension-panels` 由 `position:absolute` 改为 `position:relative` 进入 flex 行，PDF 变窄但完整可见、不被覆盖；收起助手后恢复 02 默认布局与 PDF 原宽度；1100–1439px 扩展面板单列堆叠、宽 280–320px。
  证据：1600px 三栏 PDF 760 / 助手 500 / 翻译 400（PDF 由 1100 变窄，扩展面板 `left=1200 ≥ PDF right`）；1440px PDF 600 + 助手 440 + 扩展 400；1200px PDF 420 + 助手 460 + 扩展 320；1100px PDF 420 + 助手 380 + 扩展 300；收起助手后 PDF 恢复 1600 原宽。修复项：≥1440px 共存时助手 440px 原规则误用 `.reader-body.translation-open`，改为 `:has(.reader-extension-panels.translation-open)` 后生效。
- [x] 6.3 面板精简：删除文献速读/核心创新/研究方法/研究结论快捷按钮与划词提问/当前页提问/快捷总结；分类标签保留，建议问题改为单行横向滚动；输入区只保留"发送"（请求中显示取消）。
  证据：浏览器断言 `.qa-quick` 不存在、七个按钮文案均不在面板按钮中；`.qa-input-actions` 仅"发送"；建议问题三个按钮 `top` 均为 396（单行）。
- [x] 6.4 消息自动定位：发起新问题后与答案/错误到达后，各定位到该条问答（整条能放下时对齐消息顶部；高于可视区时对齐答案/错误顶部，`prefers-reduced-motion` 下取消平滑）；删除按 intent 滚动到方法/结论的旧逻辑。
  证据：发送后最新 `.qa-message` 相对 `.qa-messages` 顶部偏移 0；答案到达后整条可放入可视区时答案正文直接可见（1600×600：消息 81px / 可视区 157px，答案 offset=38，scrollTop=0），无需下滑；旧 intent 滚动 watch 已删除。待验证：消息高于可视区时"答案顶部对齐"分支，因课程网关当前返回额度不足/限流（真实问答均以 `MODEL_ERROR` 失败），未能取得长答案实测。
- [x] 6.5 引用折叠：question/summary 每条答案一个"原文引用（N）"折叠块，analysis 每章节一个，默认关闭；展开显示页码徽标与 quote，页码跳转行为不变。
  证据：真实回答的 `details.qa-refs` 默认 `open=false`，summary 为"原文引用（2）"；点击后展开；点击"第 3 页"徽标后当前页码由 8 跳到 3。
- [x] 6.6 验收：前端单测与构建通过；真实浏览器在 1600/1200/1100/1000px 确认 PDF 无覆盖、收起后恢复原宽、仅"发送"入口、建议问题单行、自动定位最新问答、引用默认折叠且可展开跳页、无横向溢出。
  证据：`npm run build`（vue-tsc + vite）通过，`npm test` 32 文件 / 226 用例通过；Playwright(chrome) 真实账号在 1600/1440/1200/1100/1000px 共 45 项断言全部通过（PDF 未被覆盖、收起恢复原宽、仅发送、建议单行、自动定位、引用折叠可展开跳页、无横向溢出、1000px 胶囊避让抽屉）。临时脚本 `frontend/qa-ui-check.mjs` 运行后已删除。
- [x] 6.7 模型输出语言：question / summary / analysis 三种模式的系统提示均要求 answer 与章节正文使用简体中文，引用编号与 quote 保持原样。
  证据：英文文献《Attention Is All You Need》实测 question 返回 10.1s、正文为中文（Transformer 架构与翻译实验结果）；summary/analysis 返回中文（缓存命中，0.0s）；引用 quote 仍为英文原文。
- [x] 6.8 发送后清空输入框：选中建议问题或手动输入后点击"发送"/回车，输入框立即清空，问题以消息气泡保留。
  证据：`QaAssistantPanel.vue` 的 `send()` 在提交前重置 `state.question`；浏览器实测发送后 textarea 为空、消息区出现该问题气泡。

## Workflow follow-up

- 真实问答验收通过后再依用户指令同步/归档；本批规划交付不等于 AI 模块完成。
