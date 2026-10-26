# P2 PDF选区翻译（2026-10-22）

## 交付与边界

使用现有ReaderContext/文字层、ReaderPanel和认证API，未改数据库模型或迁移。仅实现选区翻译；不做OCR、全文翻译、笔记编辑/保存、题录提取或AI问答。普通结果仅保留在当前阅读器内存中，整页刷新或离开阅读器可能丢失，不宣称持久历史。P0的真实MySQL验收仍待补。

工具栏“译”展开/收起面板，不发送请求；“译选”立即翻译保留的PDF选区并展开。也可在面板点“翻译”。默认手动；实时模式在PDF选区稳定500ms且鼠标不再拖动后请求。相同选区/方向去重；新选区/文献、手动模式、收起面板都会取消或失效旧请求。成功结果带自己的来源，即使后续选区不同也不会伪装成新选区结果。方向/模式及已成功结果在收起时保留。

中英互译；原文、译文、文献ID、物理页码、方向、contextRevision、选区positions保留，供后续NoteDraft适配；本轮不调用笔记接口。只消费PDF正文文字层，普通输入框不能产生PDF选区。扫描页/缺失文字层提示不支持OCR，不伪造文本。窄屏用下半屏非模态抽屉，关闭后PDF完整可读；1100–1499宽度面板浮层，避免多个面板挤压PDF；更宽屏作为独立右侧栏。

## 模型配置与隐私

目前只适配OpenAI兼容Chat Completions协议；不是绑定某一服务商。服务商需支持该协议，其他协议实现model_service.Adapter并注册ADAPTERS即可，不改翻译业务。选择适合中英翻译且接受temperature=0的模型。真实服务商、模型和密钥未提供，当前不能验收真实译文。

通过后端私有backend/.env设置（环境变量也可覆盖）TRANSLATION_PROVIDER=openai_compatible、TRANSLATION_BASE_URL（例如https://your-provider.example/v1）、TRANSLATION_MODEL、TRANSLATION_API_KEY；.env.example无真实密钥。Windows本地启动器仍不读取项目根.env。独立TranslationSettings只读取backend/.env中的翻译配置，不改变数据库/会话设置；APP_ENV=test时不读取这份文件，防止测试使用真实密钥。复制backend/.env.example为backend/.env并私下填写，再按安全流程重启。不要把Key发送聊天、写入源码/文档/测试或提交Git。独立随机会话密钥不变。

前端不接收Key；后端SecretStr、统一安全错误，不记录原文、上游错误响应体或Authorization。Key被上游回显时拒绝结果。API地址必须HTTPS，只有回环HTTP用于开发测试；不跟随重定向。模型响应有128KiB字节上限，译文20000字符上限，超时30秒/连接5秒。不自动重试以避免额外费用。单次文本最多6000字符，每用户每分钟20次、每API进程并发2次，限流状态在内存，重启清零，不宣称分布式限流。取消浏览器请求不能保证服务商停止计算或不计费。

页面明确告知将文本发给外部服务，用户仅选择允许外发的内容。未配置时503 TRANSLATION_NOT_CONFIGURED，不回传假译文。

## API契约

POST /api/v1/documents/{documentId}/translations，现有会话、Origin和CSRF必需。后端验证owner/有效文献，并读取原PDF页数校验来源页码；不信任前端文献ID。外部请求前释放DB事务，不写翻译历史。

请求：text、sourceLanguage(en/zh)、targetLanguage(zh/en)、pageNumber(正整数)、contextRevision(非负整数)。语言须不同。响应：originalText、translatedText、source{documentId,pageNumber,sourceLanguage,targetLanguage,contextRevision,sourceType:translation}。前端另保留精确跨页选区positions作为来源结构。源码中的生产者translations.py与消费者reader/translation.ts、TranslationPanel.vue同步。

401未登录；403来源/CSRF错误；404不存在或他人文献；422输入或页码非法；429本地限流/并发或模型额度；503未配置、认证、不可用或无效输出；504模型超时。错误仅返回稳定代码和安全中文信息。

## 验证与人工操作

后端API/适配测试使用临时SQLite与MockTransport；前端状态测试使用Mock发送器；浏览器用独立8001/5175真实PDF，成功译文使用明确的Mock，未配置错误走真实后端。它们均不能代表真实模型质量。实际批次、失败修复和结果见统一LITERA_HANDOFF。

5177人工操作：刷新页面→打开自己的测试PDF→选中文字→点“译”检查原文及页码（不调用）→点面板“翻译”或“译选”→检查未配置错误/重试；配置真实模型后再验收中英互译、复制。切实时后改变选区、快速拖选、收起重开；关闭应暂停，模式保留。切换文献不允许迟到响应覆盖新文献。扫描页无法选字时显示说明，不做OCR。


用户候选服务：https://ai-gateway.devops.hello1023.com/v1，候选course-chat名称及Chat Completions兼容性尚未验证。backend/.env.example保留候选地址但模型名及密钥为空；本轮不创建实际backend/.env、不修改现有Key、不发送真实请求。不把填入地址本身视为模型可用。后续需在私有配置确认实际模型名、权限及接口后才进行用户授权的合成文本真实调用。


## 统一AI服务层增量更新

最新推荐使用backend/.env中的AI_*字段，原TRANSLATION_*仍兼容但不建议混填；AI_*优先。必须在实际验证后设置AI_MODEL_VERIFIED=true；缺配置或未验证时显示“模型未配置”，不自动调用候选网关。ModelService/ProfileResolver与用户Key隔离边界见[模型服务设计](../design/model-service.md)。翻译UI/API形状保持；本轮未重启正式本地站，新层只在隔离实例测试，当前服务健康不等于已部署该增量。

## P2-A本地加载状态（2026-10-22 14:50）
本轮已安全备份并重启5177/8002，统一AI新层和手动来源校验已加载；此前文中‘未重启’属于上一阶段历史状态。当前模型仍未配置/验证，手动点击显示安全错误；本轮仅验收手动链路，实时保留待P2-B。自动化结果见统一报告第29节。



## 2026-10-23 本轮增量状态

复用统一AI服务层和AI_*配置，新增输出Token上限（AI_MAX_OUTPUT_TOKENS默认2048）与显式scripts/verify_model.py --probe，最多两句公开合成文本/每句128输出Token，失败停止，不自动修改验证标记。未配置密钥时仍提示“模型未配置”；本轮实际backend/.env已由本地使用者创建，但检测AI_API_KEY为空，故真实请求0次、英中双向译文未验证。不能将下列Mock通过描述成真实翻译通过。

新增pdf_text.model_input_text：原始选区与定位不变，先执行异常映射保护，再在实际PDF唯一字符位置、同列相邻行及限定词形证据下合并disor-/ders、thera-/pies、ul-/trasound；未知/重复/复杂布局/真复合词原样。模型输入独立，响应仅变化时新增可选modelInputText/normalizationCount。面板来源改“文献标题 · PDF第X页”，空标题回退；重复映射警告仅一次，规范化输入可展开核对。无迁移、依赖或笔记/P2-B实现变化。

本轮最终后端142通过（临时SQLite/真实合成PDF/Mock模型），前端93通过，类型与构建通过；隔离浏览器11通过/1跳过（未提供私人PDF opt-in）。覆盖既有批注PDF导出、多文献标签及全屏。按既有安全流程预检、停服、完整联合备份20文件7432387字节并校验后一次启动，5177/8002健康200；7账号/10文献/8批注/1资产与重启前相同，资产与会话密钥哈希保持。真实MySQL仍未验收，未Docker/提交/推送。详细命令、备份路径及证据见统一LITERA_HANDOFF第31节。


## 2026-10-23：course-chat真实双向验证与本地加载

用户在私有backend/.env填Key后，本轮通过现有统一OpenAI兼容适配器向用户指定网关调用course-chat别名，固定两句普通合成文本，各最多128输出Token、无重试。两次实际HTTP200，约8.59秒：英文光学显微研究句译为“光学显微技术被广泛应用于科学研究中。”；中文句译为“Optical microscopes are widely used in scientific research.”。译文合理，证明该网关当前接受此别名及已适配对话请求形状，不保证所有模型协议或服务未来可用。

仅在上述真实成功后启用私有配置验证状态，其他配置字节保持，Key不复制、展示或提交。.env由.gitignore忽略且未跟踪。按已审核入口完成预检、stop、完整备份校验、start及数据复核，5177/8002健康200；7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。未改业务代码/结构/数据、未Docker或Git提交推送。正式网站登录后的真实选区翻译待用户人工验收；本轮不再额外调用私人PDF，详细备份和证据见统一LITERA_HANDOFF第32节。


## 2026-10-23：翻译繁忙、性能观测及来源/工具栏优化

本轮实际隔离复现旧前端cancel不等于后台结束：2次浏览器取消后，2秒Mock模型仍占槽，第三次32ms返回429 TRANSLATION_BUSY。后端新增断连取消并await清理，保留总并发2/每用户20次每分钟/原超时、不增加重试或无界队列；繁忙拒绝不再消耗调用计数。相同Mock复测取消路由约160/154ms结束，第三次正常200。历史2次429缺少错误码，不能认定均来自网关或本地。

前端真实single-flight+最多1条最新候选，500ms稳定后登记、同源重复点击复用在途Promise；429暂停自动翻译仅手动重试恢复；旧结果来源校验、乱码保护不变。补会话epoch：旧账号迟到429不影响新会话，新账号不继承实时自动外发。UI显示“当前选区译文/上一条译文”，上一条可查对应原文；toolbar“面板”开关（实时展开可能调度）与“翻译”快捷请求，同面板按钮且忙态禁用，2按钮单独自适应宽避免溢出。

新增无敏感信息的Server-Timing/网关状态响应头及translation_metrics日志。本轮2次受控真实course-chat公开短句采样：修改前浏览器2.279s/后端2.195s/网关2.166s，修改后3.176s/2.611s/2.584s，两次API/网关均200。浏览器口径含自动化点击等待，后段采样与本机检查负载存在重叠；单样本不能证明单次加速，网关span不能拆分网络/排队/推理。未观察到本轮真实网关429，Mock限流测试不能称服务商实际限流。详见docs/development/p2-translation-performance.md。

实际自动化：后端150通过（临时SQLite/合成PDF/Mock），最后PDF失败计时增量定向37通过；最终前端107通过、类型构建通过；浏览器14通过/1跳过，最后会话边界增量后定向5通过（重叠批次不相加）。按原安全流程预检/停服/联合备份验证/一次start，5177与8002健康200，7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。无.env/Key/模型配置、数据库结构或P0修改，无Docker/提交/推送。实际备份与完整证据见统一交接第33节；等待用户人工验收，不进入笔记或其他开发。
