在main基线`947dc3cc6381ce4b19d587762950f381b6e31100`上交付文献翻译、文献笔记及每用户模型配置，使“阅读PDF→个人模型翻译→保存笔记→搜索→返回来源页并高亮”在同一网站完成。

用户已确认5183统一五项人工验收全部通过。

## 行为

- PDF词语/句子/段落中英双向、手动/实时500ms、复制/错误反馈、旧请求与来源一致性保护；保留异常字体映射阻断与保守断词。
- 单用户单模型设置：保存/修改/清除或更换Key、显式连接测试、删除、脱敏状态、按用户选择；失败不回退开发者或Mock。
- 笔记CRUD、串行自动保存/CAS/草稿恢复、M:N文献复用、明确解除关联与确认全局删除。
- 原文/当前译文/历史译文插入新/当前/其他笔记，结构化来源、权限/签名/幂等，关联和来源独立。
- 本人关键词搜索，单/跨行来源页跳转、可靠PDF.js字符范围临时高亮，缺可靠范围安全降级。
- AI回答保存接口与固定Mock适配保留；真实QA权威服务尚未交付，不实现RAG或冒充真实联调。

## 安全及兼容

- Key仅后端管理；Windows默认DPAPI，Linux可用独立主密钥文件AES-256-GCM、随机nonce与owner AAD。无明文回退、不回显、不自动转换现有密文。
- URL限制公网HTTPS443；实际连接重新核验全部DNS并绑定IP，保留TLS SNI/CA，禁止重定向和代理。连接测试15秒/32输出Token/3次每用户每分钟/全局2并发；限制为单API进程内。
- 0007新增notes/note_documents，0008新增user_model_profiles；不修改既有用户/文献/批注列。本轮跨平台适配复用encryption_scheme，无新迁移。
- Compose增加非秘密开关/既有AI配置传递；可选compose.user-models.yaml只为api挂载外部主密钥。实际backend/frontend构建上下文排除dotenv变体、密钥、数据库及缓存。
- 保留此前`db.refresh(doc)`时间戳候选及兼容`attachment.sha256`字段。SQLite通过不代表P0真实MySQL已验收，请明确审阅该候选。

## 验证

- 后端全量452通过/1 POSIX专项跳过，补充新库迁移/离线MySQLDDL/依赖3通过：455项通过。
- 前端218通过，类型及生产构建通过；构建到独立cache，未覆盖在线dist。
- 浏览器65通过/2私人PDF可选跳过，含笔记、翻译、导出、批注、标签/全屏/长文、来源定位及用户模型链路；全部临时SQLite与Mock/受控HTTP。
- 5177/5180/5183数据库与PDF哈希和完整性不变，5183健康200；本轮未重启、迁移现有实例、读取真实Key或请求真实模型。
- Compose YAML仅静态语法校验；没有执行Linux镜像构建、POSIX实际权限、真实MySQL或真实QA。模型质量/HTTP逐次记录不以Mock代替。

## 部署与协调

见`docs/delivery/deployment.md`：先用独立项目名/端口/卷与外部主密钥做新实例验收；已有数据升级需联合备份和副本恢复验证再单独批准。禁止drop/down -v/prune/自动覆盖恢复。DPAPI跨主机不能解密，需本人重填或另行审批迁移。

见`docs/delivery/team-integration.md`：06需权威UUID回答ID/正整数修订/owner和版本化引用，05需fileHash+extractionVersion+chunk证据读取。当前D1单文献回答；多文献笔记不等于多文献QA。ModelService/Vault可复用，但当前Resolver限定translation，QA能力与预算必须另行明确。

旋转/跨物理页高亮/OCR、真实QA、真实MySQL正式验收不属于本PR已验证范围。不含真实.env、用户数据库/PDF、密钥或密文备份、缓存/构建产物及其他项目。
