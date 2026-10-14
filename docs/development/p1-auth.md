# P1 注册登录开发与验收记录

日期：2026-10-14。范围：01-literature-management 的任务1.1–1.8；负责人 Jensen Zhang。本轮仅实现普通用户账号认证，文献库是明确标注的占位页。

## 已实现

- Vue 3、TypeScript、Element Plus 登录/注册页面，自有 Litera SVG 标识、白灰背景与北大红主题；移动端自适应。
- FastAPI 注册、登录、退出、会话查询、当前用户查询及显示名称修改，直接读写数据库，无模拟业务接口。
- SQLAlchemy + Alembic 的0001_auth迁移，只创建users和sessions；MySQL由Compose提供。测试数据库litera_test独立于litera。
- Argon2id密码哈希；随机会话Cookie为HttpOnly、SameSite=Lax；数据库只保存会话token的SHA-256摘要。退出撤销，过期401；凭证不进localStorage。
- 登录/注册校验Origin；其他写入同时校验Origin和会话绑定CSRF token。客户端不能设置用户ID或角色，非法字段返回422。
- 标准错误包络与requestId、无缓存私有API、前后端字段校验和失败反馈；登录成功进入/library。
- Nginx提供静态前端、SPA回退与/api代理；数据库/API没有发布宿主机端口，外部只访问8080。

## 认证接口

| 接口 | 输入/结果 |
| --- | --- |
| POST /api/v1/auth/register | email/password/displayName；201，注册后不自动登录 |
| POST /api/v1/auth/login | email/password；user、csrfToken及会话Cookie |
| GET /api/v1/auth/session | 当前user与csrfToken，无有效会话401 |
| POST /api/v1/auth/logout | Origin与X-CSRF-Token；204，撤销会话 |
| GET /api/v1/users/me | 当前用户DTO，不返回密码或token |
| PATCH /api/v1/users/me | displayName；需要Origin与X-CSRF-Token |
| GET /api/v1/health | 检查数据库连接，返回status=ok |

完整约定见[公共API契约](../design/api-contracts.md)。注册邮箱规范化为小写并唯一；显示名称去首尾空白，长度1–80；密码默认8–128字符。会话默认24小时；注册/登录合计每IP默认20次/60秒，当前为单API进程内限流，进程重启会清空计数。

## 配置与启动

项目[README](../../README.md)提供Windows CMD完整步骤。初始化脚本生成本地.env，不覆盖已有文件。真实秘密与构建/测试产物被.gitignore排除，.env.example只提供变量名与非秘密默认值。

IMAGE_REGISTRY默认public.ecr.aws/docker/library，因本机Docker Hub认证服务器曾连接超时，改用Docker Official Images的公开ECR源；可自行改为docker.io/library。没有修改全局Docker配置。MySQL数据保存在litera_mysql_data命名卷，正常docker compose down保留注册数据。

收到用户“Docker由本人手动负责”的指令后，不再自动拉取、构建或启动容器。用户已提供更新后的成功日志；只读检查db/api/nginx均healthy，健康接口ok。用户随后授权在已有容器运行pytest，该测试22项通过；Docker拉取、构建及启动继续由用户手动负责。

## 测试证据

| 检查 | 结果/环境 |
| --- | --- |
| 后端pytest | 22通过；本地隔离SQLite库，使用Alembic迁移 |
| 前端Vitest | 7通过；校验、错误契约、CSRF发送、会话401导航回归 |
| 生产前端构建 | vue-tsc与Vite通过；JS约208KB |
| Playwright真实浏览器 | 2通过；用户手动启动的Nginx/FastAPI/MySQL服务，无业务API替身 |
| Docker健康检查 | 用户手动构建启动后，三服务healthy，HTTP健康接口ok |
| MySQL版pytest | 22通过；用户明确授权后在已有容器的独立litera_test库执行 |

浏览器覆盖注册字段/确认密码、重复邮箱、无效凭证、登录后路由、刷新会话、资料更新跨刷新、退出及受保护路由拦截；另测390px移动端无横向溢出和网络失败提示。API替身仅用于前端单测及明确的断网模拟，不用于业务完成证明。浏览器测试会在开发库创建e2e-前缀验证账号。

测试中发现退出后的会话查询401重复触发路由导航，已修复：会话探测401由路由守卫处理，其他私有API的401才发失效事件；前端回归和真实浏览器验证均通过。

## 边界与后续

无管理员、文献上传/检索/分类、PDF、翻译、笔记、提取或AI服务；相关OpenSpec任务保持未勾选。本轮不归档整个01，不进行commit/push。下一轮须等待用户体验并明确启动P2。

生产部署需要HTTPS和COOKIE_SECURE=true；本轮只交付本机开发环境。测试客户端依赖有一条httpx兼容弃用警告，不影响通过结果，后续更新测试工具时处理。MySQL版pytest已通过；用户已认可注册页、文献库占位页和个人资料页；当前登录布局已完成修复。
