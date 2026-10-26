# 用户模型设置 v1（独立 Windows 预览）

本功能由 Change07 管理，复用 ModelProfile、ProfileResolver、ModelService、OpenAICompatible 和既有翻译/笔记回执。没有实现真实问答或改变旧来源结构。

## 安全存储与隔离

`user_model_profiles` 每用户一行：owner_id PK/FK、随机revision、provider、base_url、model、encrypted_key(BLOB)、encryption_scheme、tested_revision、updated_at。所有查询和修改的owner来自登录会话，不接受浏览器ownerId。PUT/DELETE/test使用expectedRevision；每次保存随机换revision并撤销验证，防止覆盖及删除重建ABA。原笔记、关联、账号、文献表不变。

WindowsSecretVault使用 **DPAPI CurrentUser**，用途和用户ID作为附加熵；不使用LocalMachine。API Key只在服务端调用期间解密，数据库保存受完整性保护的密文，操作系统账号管理主密钥，主密钥不在数据库或Git。不同用户行不能直接互换密文。缺少Windows安全后端即拒绝启用，不降级明文。将数据库迁移至其他机器/Windows服务账号时，需由用户重新填写Key；数据库备份不等于DPAPI主密钥备份。服务器账号被攻破超出该存储保护边界。未来Linux/托管部署需增加独立密钥管理适配器，不能直接启用明文或共享env Key。

微软说明：[CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata)。本地Windows实际DPAPI往返、错误owner和篡改拒绝已自动测试。

## 接口契约

全部使用现有会话鉴权，写操作验证Origin和CSRF，响应no-store。API不回显Key、尾号或密文，只返回hasApiKey。

| 方法 | 路径 | 输入/效果 |
| --- | --- | --- |
| GET | /api/v1/user-model | available与本人的profile摘要；未开启安全功能时available=false且不访问新表 |
| PUT | /api/v1/user-model | provider/openai_compatible、baseUrl、model、可选apiKey、clearKey、expectedRevision；无Key表示保留，clearKey显式清除；只保存不调用模型 |
| DELETE | /api/v1/user-model | expectedRevision；只删除本人配置，已有笔记/译文不变 |
| POST | /api/v1/user-model/test | expectedRevision；只测试已保存版本，固定非私人提示，32输出Token，最多15秒、3次/用户/分钟、2个并发，无自动重试；通过后仅验证该revision |
| POST | /api/v1/documents/{id}/translations | 原字段保持；新增可选modelSource=developer/user、modelRevision。旧请求默认developer。user需本人已测试版本，失败绝不回退 |

翻译返回可选`modelConfiguration:{source:'user',revision}`。PDF/文献/语言/原文/页码、签名翻译Proof和笔记来源保持旧格式，Key不进入浏览器响应。请求返回后重新读配置revision，若改变/删除返回409；前端切换配置使旧响应失效。模型设置事件/窗口focus刷新摘要，不自动发起模型请求。

## SSRF与费用约束

用户地址仅公网HTTPS/443；禁止userinfo、query、fragment、编码/反斜线/点段路径、私网、回环、链路本地、元数据、IPv4映射/转换及保留地址。保存只做无网络格式验证；真正连接时解析所有A/AAAA，任一不安全即拒绝。TCP连接绑定校验后的数值IP，TLS仍以原域名做SNI与证书校验；不二次解析域名，不跟随重定向，不读取代理环境，不重试。固定POST /chat/completions，用户不能指定任意方法/头。错误不返回上游响应体。翻译沿用20次/用户/分钟、2并发，用户模型新增35秒总时限、128KiB响应及2048输出Token上限。

依据：[OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)。`PublicModelTransport`借用httpx/httpcore内部池挂接点，所以显式固定现有httpcore1.0.9/httpx0.28.1，不重复安装；升级传输库须重跑IP绑定、TLS域名及重定向测试。

## 模型验证含义

保存不验证、勾选或配置环境变量不验证。连接测试只能证明该版本返回有效对话结构和非空文本，不能替代翻译质量验收。真实独立预览APP_ENV=development，禁用开发者.env加载且不启用Mock；测试fixtures APP_ENV=test，其回执和译文始终标明isolated_mock。

## 迁移与旧环境

0008仅增加一表，不改0007；非空用户配置表禁止自动downgrade。先临时0007合成数据备份/恢复/完整性，再升级验证原行/文件不变。新5183实例初始化0007后做完整备份与恢复验证，再升级0008，API启动只检查不迁移。5177、5180未打开数据库写连接或执行迁移；5180仍0007。

**新增head使旧local-site/notes-preview启动器的版本guard拒绝再次启动；本轮没有绕过或修改旧guard。** 后续如恢复旧环境，须先单独审核固定旧版本启动方案或备份后的正式迁移，不能直接重启绕过。现有主机部署Docker仍完全不操作。


## Linux GitHub交付补充
Windows auto保持DPAPI；Linux auto在配置独立文件时选择AES，或显式USER_MODEL_SECRET_BACKEND=aesgcm_file。USER_MODEL_MASTER_KEY_FILE只能是后端可读的绝对文件路径，文件为32字节随机密钥的base64，POSIX0600/0400且非符号链接；密文采用aes256gcm-file-v1、随机12字节nonce、owner+用途AAD及128bit认证tag。缺文件/错误长度/宽权限/篡改/错误owner安全拒绝，不明文回退。
复用0008.encryption_scheme，不新增迁移，不自动转换DPAPI或轮换真实密钥。旧方案在新Vault中安全拒绝，用户必须明确重填或清除；需要迁移真实密钥时另行审核。Linux Docker和POSIX真实权限仍待目标环境验证，不能用Windows AES单测冒充。
具体Compose secret、备份和恢复步骤见[交付部署](../delivery/deployment.md)。
