## Why
已验收的统一 AI 层只读取开发者配置。用户需要隔离、可更换、可在网页验证的自有模型，不能共享开发者密钥。
## What Changes
- 认证用户单个 OpenAI Compatible 配置的 CRUD、显式连接测试及翻译选择。
- Windows DPAPI CurrentUser及Linux独立主密钥文件AES-GCM加密，密钥管理与数据库分离；无安全能力时关闭功能。
- 公网 HTTPS/443、DNS 连接绑定、防重定向、速率/并发/响应大小/时长限制。
- 仅新隔离实例新增 0008；5177/5180 不迁移、不重启、不改变 Mock 模式。
## Capabilities
### New Capabilities
- `user-model-settings`: 个人模型设置、安全验证及统一翻译接入。
### Modified Capabilities
## Impact
新增 user_model_profiles；复用认证/CSRF/模型服务/翻译回执/笔记来源。默认禁用新功能，旧客户端请求保持开发者配置语义。当前统一验收站使用127.0.0.3:5183的单API/静态前端，独立SQLite/PDF/会话；不再使用8004常驻代理。无真实QA、MySQL部署、Docker或Git发布。
