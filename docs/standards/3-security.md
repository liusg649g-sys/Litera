# 3-安全开发规范

> 跨仓适用说明：规范约束两仓后续开发，本文实现快照来自Litera-test。原Litera目前仅01/02、迁移至0006；03/04/07及0007/0008尚未合并，相关“现有”描述只属于Litera-test，在原项目按待接入要求理解。文件同步不等于代码、脚本或部署已合并，先查本仓实际文件；总表见[规范索引](README.md)。

适用：全部代码、规则/技能、上传内容、构建与对外接口。三条硬约束常驻 [AGENTS.md](../../AGENTS.md)。普通用户只有本人私有数据；无管理员/班级角色和JWT刷新令牌系统。

## 十四项约束

| ID / 课件条目 | 具体约束 | 检查/验证方式与依据 |
| --- | --- | --- |
| S01 默认拒绝 | 新API先登记下方授权清单；除明确公开入口外必须依赖会话，写操作还依赖Origin/CSRF。开关/Vault/依赖不满足就拒绝或禁用 | 检查路由工厂依赖和未登记端点；匿名调用新增私有路由应401。当前没有自动拦截“未登记路由”的全局白名单，集中门禁待落实 |
| S02 逐资源授权 | owner只取session.user_id；每次访问同时校验文献、文件、笔记及嵌套资产/引用关系，不相信客户端owner或旧ReaderContext | A/B账号互换ID重放读写；普通资源返回与不存在相同404语义；现有owned_document/owned_note/owned_asset及测试。SQL带owner过滤等价于先取行再判，不强迫改查询方式 |
| S03 附件读取 | 文件必须挂在已授权文献下；PDF/资产不进nginx公开目录，不开放仅凭任意文件名/磁盘路径的通用下载接口 | 匿名、B账号、错误document/asset组合读取应拒绝；核对content/reader-assets和nginx root/卷挂载 |
| S04 越权失败场景 | 新资源读/写/删除/下载/派生操作各配匿名、本人、他人/错误关联用例；若未来新增角色，再补低权限访问高权限功能用例 | OpenSpec场景与用例逐项映射；当前只有普通角色，不能虚构管理员越权已测 |
| S05 认证/会话 | 保留Argon2口令哈希、不透明随机会话ID和库内token哈希；登录轮换、退出/过期撤销；改密码撤销本人全部会话；不提供默认演示密码 | test_auth检查Cookie/退出/改密/错误密码等；密码不trim、不回显；日志/URL不得带token |
| S06 凭证存放 | 当前HttpOnly、SameSite=Lax的litera_session Cookie；生产Secure+HTTPS；CSRF仅内存。禁止认证token进localStorage/sessionStorage/URL | 检查auth.ts、main.py和浏览器存储；草稿/模型模式可按账号放sessionStorage，但不得混入Key。Lax是现有同源会话方案例外，不伪造Strict/JWT实现 |
| S07 密钥/机密 | 部署变量/私有.env或独立主密钥文件提供机密；Git/Docker忽略先于入库；个人Key经Vault加密，只返回hasApiKey等状态，保存后清空输入；泄露按下方流程轮换 | 查.gitignore、两构建上下文.dockerignore、model_secrets、user_models；用合成Key验证响应/日志不回显；禁止在扫描输出中打印真实Key |
| S08 外部内容不可信 | PDF、笔记、译文、模型回答、工具/技能描述均是数据；模型输入放user消息，system明确不执行原文指令；来源不能代替授权，Mock不能冒充真实回答 | 查看model_service.translation_messages；用含“忽略系统指令”及HTML文本的隔离样本验证。真实模型抗注入效果须另测，不以静态提示词当证明 |
| S09 出站地址 | 个人模型只允许公网HTTPS443，连接时验证全部DNS答案并固定安全IP，保留TLS/SNI；禁私网/本机/元数据/重定向/代理。新回调或拉取接口需等价策略 | test_user_models中的unsafe URL/DNS rebinding/transport用例；开发者默认模型由管理员配置，是现有另一通路，不宣称也经过同样强校验 |
| S10 输入白名单 | Pydantic约束类型/长度/枚举、拒未知body字段；页码/坐标/版本/文件真实结构服务端核验；上传名只展示、存储键服务端生成且根目录约束 | 传未知owner、NaN/Infinity、越界页码、伪装PDF、路径穿越；检查拒绝后数据库/文件不变；见schemas/documents/annotations |
| S11 输出转义/参数绑定 | Vue插值/文本节点展示不可信内容，不用v-html执行原文/译文；SQLAlchemy绑定参数，动态排序白名单；不把外部文本拼进shell | 含引号、SQL片段、script/事件属性的输入不执行且原样可读；test_notes纯文本、文献检索测试；新增富文本须独立安全设计 |
| S12 敏感数据 | 响应不回密码哈希、会话hash、密钥密文、磁盘路径；日志不记Key/正文/原始上游响应。复用固定ModelFailure/统一error处理；字段校验只回字段名/类型 | 合成机密注入错误路径，检查日志与响应。当前全局logging.exception仍可能包含内部堆栈，不把它当作已完成全日志脱敏；新增异常需审查并跟踪缺口 |
| S13 依赖/许可证 | 新增依赖写用途、版本、许可证、替代评估；沿用锁文件。新依赖许可证默认允许MIT/BSD-2-Clause/BSD-3-Clause/Apache-2.0/ISC，字体OFL-1.1随附许可；其他须负责人审阅并记录，不能默认未知即允许 | 对比package-lock/requirements和许可证文件；当前全量依赖尚无完整许可证审计，规则是增量要求，不是合规认证 |
| S14 漏洞扫描 | 新依赖/锁变化、交付前执行依赖与机密扫描并记录工具、日期、数据库更新时间；达到Critical/High且影响交付产物时阻断，24h内确认处置，分别目标48h/7天修复或记录有期限的缓解例外 | 前端可用npm audit --omit=dev，后端用隔离环境pip-audit -r requirements.txt；不得自动升级/执行npm audit fix。当前未装配完整CI阻断，网络不可用记待验证，不能当通过 |

## 授权清单与核对方法

这是新增端点的登记基线，不是已实现的全局路由白名单。新增/变更端点须写到相应行并列出生产者；请求参数里的owner/user/role字段不授予权限。

| 路由族/入口 | 允许者及服务端校验 | 生产者 |
| --- | --- | --- |
| 前端静态页、`/api/v1/health`、`/api/docs`、`/api/openapi.json` | 明确公开；health只探数据库，不返回机密；是否对公网保留API文档由运维决定 | nginx.conf、main.py |
| POST `/api/v1/auth/register`、`/auth/login` | 访客可调用；Origin+IP限流，不能要求已有会话 | main.py |
| GET `/auth/session`、`/users/me` | 有效会话，仅本人 | main.py |
| `/auth/logout`、`/auth/password`、PATCH `/users/me` | 有效会话+Origin/CSRF；密码变更复核当前密码 | main.py |
| `/documents`、`/folders`、`/tags`、`/reading-history`、`/trash`、`/cleanup-jobs`、`/library/config` | 有效会话；列表仅本人；写操作Origin/CSRF；文献/分类/清理任务关联逐项核对 | documents.py、library.py |
| `/documents/{id}/content`、`/progress`、`/annotations`及收据、`/reader-assets`、`/annotated-pdf` | 文献owner/状态；资产、批注、收据必须属于同文献/owner；写和导出需Origin/CSRF | documents.py、annotations.py、reader_assets.py、pdf_exports.py |
| `/documents/{id}/translations` | 写请求鉴权+文献/页码核验+模型来源/配置owner与revision复验 | translations.py |
| `/notes`、笔记关联/摘录/搜索/配置 | 本人笔记；新增关联、PDF来源、译文证明、AI回答各自复核，不接受客户端伪造sources | notes.py、note_captures.py |
| `/user-model`、`/user-model/options`及测试 | 会话本人；写/测试Origin/CSRF；开关、Vault、revision、验证状态 | user_models.py |
| 隔离模拟问答接口 | 仅显式隔离验收模式及fixture允许；普通部署不得暴露成真实QA | answer_sources.py、note_captures.py |

核对404：同一资源族分别用不存在ID、另一账号ID测试，比较HTTP、error.code和安全文案；排除requestId等动态值。不能照抄课堂案例“完整响应逐字节相同”，也不能将所有领域404强制改成一个code。

## 机密泄露处置与轮换

由**部署实例持有人**执行轮换，模块负责人协助定位；发现人报告机密种类、影响范围、时间，不粘贴原值。README链接本节作为处置入口。

1. 停止受影响调用/交付，确认泄露是否进入Git历史、日志、镜像层、前端产物或备份；用受控扫描，不输出原值。删文件不足以处理已泄露历史。
2. API Key在服务商撤销旧Key，由本人重新填写、保存并主动测试；默认共享模型Key由部署者更新服务端配置。不能用其他账号Key临时代替。
3. SESSION_SECRET泄露：部署者生成新值并安排撤销既有会话，验证旧会话拒绝；改环境变量不等于数据库里所有会话已撤销。数据库密码须先协调MySQL实际账号与调用方，再更新配置，不能只改.env。
4. Vault主密钥泄露/丢失：保留受控备份与现有密文，停用个人模型。当前无自动主密钥轮换/跨机转换工具；另行设计副本验证的重加密方案，或用户显式重填；绝不直接替换文件并宣称旧Key已迁移。
5. 重建受影响镜像/前端、验证旧凭证失效和合法功能恢复，记录脱敏证据；Git历史清理和外部发布需单独授权，轮换不等于自动允许重写历史。

## 违反时

报Sxx、入口/资源、可复现步骤、是否拿到越权数据或发生写入。越权、明文机密、执行外部内容属于阻断项；只改文案不算整改。移除授权的验证只在临时样本/隔离测试中做，不移除现有业务服务的校验。集中授权门禁、全日志脱敏及全量许可证/漏洞扫描仍待落实，按S01/S12/S13/S14跟踪。
