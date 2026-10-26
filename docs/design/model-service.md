> 2026-10-26交付状态：个人模型设置与统一翻译已实现并验收。以下涉及“未来个人设置”的段落属于早期设计；当前实现为user_models.snapshot、model_secrets的DPAPI/AES文件Vault，未来QA需另行授权capability而非直接宣称已接入。见[GitHub交付](../delivery/github-delivery.md)。

# 可更换模型服务层

## 调用边界

认证请求 → 请求级ProfileResolver → ModelProfile → ModelService.complete(messages, principal_id, profile) → Adapter.complete(messages, profile)。翻译的语言方向/提示词仅在model_service.py；HTTP、错误脱敏、统一结果校验及适配器注册在ai_service.py。翻译API不拼服务商URL、不读取Key、不修改数据库。

ModelSettings只读取开发者私有backend/.env或环境变量，独立于数据库/会话配置。推荐AI_PROVIDER、AI_BASE_URL、AI_MODEL、AI_API_KEY、AI_MODEL_VERIFIED；兼容原TRANSLATION_*名称，AI_*优先，请只使用一组。模型服务地址包含/v1而不含/chat/completions。OpenAI兼容服务可只改配置，协议不兼容时实现Adapter.complete并注册，不改翻译业务。

backend/.env.example无真实密钥。实际.env被Git忽略，Key以SecretStr表示且不进入profile/settings的repr，无前端Key字段、公开日志或错误响应。共享模型层拦截适配器回显Key；适配器必须遵循不记录原文/认证头/上游错误体约定。请求级profile不能放到全局用户缓存，ADAPTERS全局注册表只包含无密钥适配器实例。

AI_MODEL_VERIFIED默认false。缺字段、未支持适配器或未确认模型均拒绝发请求，页面显示“模型未配置”。这个标记是开发者私下验证后的确认，不是自动网络检测，不证明服务永久可用或替代真实模型测试。候选网关和course-chat仍未验证。本轮没有真实模型调用。

## 开发者与最终用户配置必须分开

当前DeveloperProfileResolver仅提供本地开发者自用的服务配置，scope=developer；它不是最终用户密钥存储。ModelProfile携带scope、owner_user_id及验证状态，Key排除repr。用户scope必须与已认证principal_id一致；不允许请求体指定任意用户配置归属。

未来个人设置应另行实现：每用户授权查询、加密密钥存储和脱敏展示/更新/撤销、验证状态及出站地址策略，再实现ProfileResolver.resolve(principal_id, capability)。通过FastAPI的translations.model_resolver依赖接入，不需要修改翻译提示词或传输逻辑。用户选择自有配置但缺失/失效时必须明确报错，不能静默改用其他用户或全局Key。个人配置不能复用get_model_settings的全局开发者配置缓存；profile必须按当前认证用户解析。未来存储、迁移、地址访问控制、密钥生命周期均需单独设计和授权。

本轮只提供接口和归属校验，不实现个人配置UI、用户Key写入接口或数据库表，不对外接受自定义Key/URL字段。不存在“把用户Key保存为全站共享变量”的实现。

## 测试与加载

测试使用临时SQLite及FakeAdapter/MockTransport，覆盖适配器切换、配置别名优先级、未验证禁止调用、Key回显拒绝、repr脱敏、用户归属及请求依赖注入。APP_ENV=test时不读取开发者私有backend/.env；测试没有真实模型质量证据。

修改配置后，需按现有安全流程备份并重启后端加载；本轮未重启5177，不操作当前SQLite/PDF数据。当前运行实例仍是上一轮已加载代码，新统一层仅在隔离测试实例中验证；不得将健康200当作本轮新层部署证据。

## 后续部署更新（2026-10-22 14:50）
P2-A已通过原安全入口备份后重启，本设计统一层现已加载到5177后端。此前‘当前实例旧代码’是上一阶段时点说明。模型仍未配置或真实验证，不能以健康200代替真实模型测试。



## 2026-10-23：真实调用前的有界验证入口

当前统一配置继续使用 AI_PROVIDER、AI_BASE_URL、AI_MODEL、AI_API_KEY、AI_MODEL_VERIFIED；新增 AI_MAX_OUTPUT_TOKENS（默认2048，16–4096），仅影响输出预算，不改翻译业务或数据库。OpenAI兼容适配器发送 max_tokens；finish_reason=length 时提示缩小选区，不把被截断的译文作为成功结果。协议不支持这些参数时应明确报告不兼容，不自动无限重试。

本机私下配置 backend/.env：先确认文件不存在时才复制 backend/.env.example，已有文件仅补所需AI字段，不覆盖数据库或其他配置。候选 Base URL 为用户提供的网关，course-chat 是待验证别名；保持 AI_MODEL_VERIFIED=false。密钥仅本机编辑，不放聊天、前端、Git或报告。复制/编辑是使用者本地操作说明，不能当作已经执行的配置。

`backend\.venv\Scripts\python.exe scripts\verify_model.py` 仅检查配置完整性，不发请求。显式附加 `--probe` 才用两句公开合成文本调用实际适配器，每句最多128输出Token，超时或首次失败即停止，不读取PDF、不连接数据库、不自动更改.env/verified标记。此入口为了核验尚未验证的配置直接使用协议适配器，网站业务仍必须经过ModelService的验证门。两次返回有效内容后仍需审查译文合理性，再更新同一配置的验证状态并安全重启加载；不把打开标志当作真实测试。

错误认证/额度/超时/无效结构/密钥回显等自动化用例使用MockTransport，不能替代真实上游失败环境验证。实际本轮是否完成真实调用以及服务是否已加载，以统一LITERA_HANDOFF最新记录为准。


## 2026-10-23：course-chat真实双向验证与本地加载

用户在私有backend/.env填Key后，本轮通过现有统一OpenAI兼容适配器向用户指定网关调用course-chat别名，固定两句普通合成文本，各最多128输出Token、无重试。两次实际HTTP200，约8.59秒：英文光学显微研究句译为“光学显微技术被广泛应用于科学研究中。”；中文句译为“Optical microscopes are widely used in scientific research.”。译文合理，证明该网关当前接受此别名及已适配对话请求形状，不保证所有模型协议或服务未来可用。

仅在上述真实成功后启用私有配置验证状态，其他配置字节保持，Key不复制、展示或提交。.env由.gitignore忽略且未跟踪。按已审核入口完成预检、stop、完整备份校验、start及数据复核，5177/8002健康200；7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。未改业务代码/结构/数据、未Docker或Git提交推送。正式网站登录后的真实选区翻译待用户人工验收；本轮不再额外调用私人PDF，详细备份和证据见统一LITERA_HANDOFF第32节。


## 2026-10-23：翻译繁忙、性能观测及来源/工具栏优化

本轮实际隔离复现旧前端cancel不等于后台结束：2次浏览器取消后，2秒Mock模型仍占槽，第三次32ms返回429 TRANSLATION_BUSY。后端新增断连取消并await清理，保留总并发2/每用户20次每分钟/原超时、不增加重试或无界队列；繁忙拒绝不再消耗调用计数。相同Mock复测取消路由约160/154ms结束，第三次正常200。历史2次429缺少错误码，不能认定均来自网关或本地。

前端真实single-flight+最多1条最新候选，500ms稳定后登记、同源重复点击复用在途Promise；429暂停自动翻译仅手动重试恢复；旧结果来源校验、乱码保护不变。补会话epoch：旧账号迟到429不影响新会话，新账号不继承实时自动外发。UI显示“当前选区译文/上一条译文”，上一条可查对应原文；toolbar“面板”开关（实时展开可能调度）与“翻译”快捷请求，同面板按钮且忙态禁用，2按钮单独自适应宽避免溢出。

新增无敏感信息的Server-Timing/网关状态响应头及translation_metrics日志。本轮2次受控真实course-chat公开短句采样：修改前浏览器2.279s/后端2.195s/网关2.166s，修改后3.176s/2.611s/2.584s，两次API/网关均200。浏览器口径含自动化点击等待，后段采样与本机检查负载存在重叠；单样本不能证明单次加速，网关span不能拆分网络/排队/推理。未观察到本轮真实网关429，Mock限流测试不能称服务商实际限流。详见docs/development/p2-translation-performance.md。

实际自动化：后端150通过（临时SQLite/合成PDF/Mock），最后PDF失败计时增量定向37通过；最终前端107通过、类型构建通过；浏览器14通过/1跳过，最后会话边界增量后定向5通过（重叠批次不相加）。按原安全流程预检/停服/联合备份验证/一次start，5177与8002健康200，7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。无.env/Key/模型配置、数据库结构或P0修改，无Docker/提交/推送。实际备份与完整证据见统一交接第33节；等待用户人工验收，不进入笔记或其他开发。
