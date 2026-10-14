# Litera 开发交接

更新时间：2026-10-14。项目根目录：`D:\PKU\Projects\Litera`。
本文件是开发快照；详细需求以现有 OpenSpec 与设计文档为准。
下一轮任务：**文献库主界面开发**。本会话仅整理文档，未开始该任务。

## 新会话先读

- [README：启动、配置及测试](README.md)
- [六模块总览](openspec/changes/README.md)
- [01 任务清单](openspec/changes/01-literature-management/tasks.md)
- [01 方案](openspec/changes/01-literature-management/design.md)及[文献库规约](openspec/changes/01-literature-management/specs/literature-library/spec.md)
- [总体设计索引](docs/design/README.md)、[UI 规范](docs/design/ui-guidelines.md)
- [API 契约](docs/design/api-contracts.md)、[数据模型](docs/design/data-model.md)、[阶段计划](docs/design/delivery-plan.md)
- [P1 认证验收记录](docs/development/p1-auth.md)、[P1 UI 验收记录](docs/development/p1-ui.md)

## 已实现页面与代码入口

- Vue 3 + TypeScript + Element Plus；B/S 架构，前后端分离。
- `/login`、`/register`：真实登录注册、字段校验、错误反馈和模式切换。
- `/library`：受认证保护的文献库占位页，无文献业务。
- `/profile`：当前用户信息展示、显示名称修改与持久化。
- 登录成功跳转文献库，刷新恢复会话，退出撤销会话并返回登录。
- 入口：`frontend/src/views/`、`auth.ts`、`api.ts`、`router.ts`。
- 品牌为 Litera，中文名“科研文献智能管理与协作平台”；自有 SVG Logo。
- 颜色集中在 `frontend/src/theme.css`，主色 `#9B0000`，状态色独立。
- 保留白灰简约风格与账号页左右分栏；详细交互遵守现有 UI 规约。

## 已实现后端与数据

FastAPI + SQLAlchemy + Alembic；实现集中在 `backend/app/`。
以下为实际接口，公共 API 文档内的其他业务接口仍属于规划：

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| POST | /api/v1/auth/register | 注册；成功后需另行登录 |
| POST | /api/v1/auth/login | 验证凭证、设置会话 Cookie |
| GET | /api/v1/auth/session | 会话恢复与 CSRF token |
| POST | /api/v1/auth/logout | 撤销会话 |
| GET / PATCH | /api/v1/users/me | 查询本人资料 / 修改显示名称 |
| GET | /api/v1/health | 数据库连接健康检查 |

- MySQL 8.4；迁移 `backend/migrations/versions/0001_auth.py` 仅创建 users、sessions。
- 文献、附件、分类、标注、笔记、提取与 AI 数据表均未实现。
- 密码使用 Argon2id；数据库仅保存会话 token 的 SHA-256 摘要。
- HttpOnly、SameSite=Lax Cookie；凭证不存 localStorage。
- 注册登录校验 Origin，其他认证写请求同时检查会话绑定 CSRF。
- 无效凭证统一提示；邮箱唯一；禁止客户端覆盖身份或角色。
- 错误响应包含 requestId；注册登录具有单进程内 IP 限流。

## Docker 与本机开发配置

- `compose.yaml`：db / api / nginx 三服务，健康检查与启动依赖齐备。
- 前后端 Dockerfile 已提供；Nginx 提供静态资源、SPA 回退及同源 API 代理。
- 默认只有 Nginx 对外发布 8080；MySQL、API 留在 Compose 网络。
- 命名卷为 `litera_mysql_data`；API 启动先执行 Alembic 升级。
- `.env.example` 为配置模板；`scripts/init_env.py` 生成秘密且不覆盖已有 .env。
- .env、依赖、构建/测试产物和 docs 下 Word 文件由 .gitignore 排除。
- Docker 拉取、构建、启动均由用户手动执行，命令见 README。
- 开发命令使用 Windows CMD；不要默认使用 PowerShell。
- 不修改全局 Docker 配置，不自行 commit 或 push。

## 六个 OpenSpec change 状态

全部完成规划，最近严格校验 6/6 通过；未归档，规划完成不等于业务完成。

| Change | 当前状态 | 负责人 |
| --- | --- | --- |
| 01-literature-management | P1 1.1–1.8、UI 4.1–4.4 完成；P2 2.x / 3.x 全部未完成（12/24） | Jensen Zhang |
| 02-pdf-reader | 全部待开发（0/12）；需 01 P2 验收后另行启动 | Jensen Zhang |
| 03-translation | 全部待实现（0/6） | Siguo Liu（其他成员） |
| 04-literature-notes | 全部待实现（0/6） | Siguo Liu（其他成员） |
| 05-metadata-extraction | 全部待实现（0/7） | Jialu Ma（其他成员） |
| 06-ai-qa | 全部待实现（0/8） | Jialu Ma（其他成员） |

## 测试与验收边界

- 最近前端：构建通过；Vitest 7 项、Playwright auth-ui 10 项通过。
- UI 覆盖校验、主题、三种桌面和两种窄屏，以及登录注册切换。
- 五种尺寸注册页截图与最近调整前完全一致；文献库、资料页源码未改。
- 此前认证验收：SQLite pytest 22 项、独立 litera_test 的 MySQL pytest 22 项通过。
- 此前真实认证 Playwright 2 项通过；并非在最新文档会话重新执行。
- auth-ui 使用本地 Vite，仅隔离匿名会话及指定错误响应，不能代替真实业务验收。
- 用户已认可注册页、文献库占位页和个人资料页；下一轮文献库业务验收尚未开始。
- 最新源码是否已由用户重新构建部署尚未确认；Docker 镜像不会自动随源码更新。

## 限制及下一轮边界

- 本机开发环境已交付；生产 HTTPS、Secure Cookie 部署尚未交付。
- 限流目前不跨进程共享；测试存在 Starlette/httpx 弃用警告，不影响已通过结果。
- 本阶段按用户授权提交并推送；新会话先检查 git status，保留后续本地改动。
- 下一轮从 01 的 P2 与 UI 规约规划文献库主界面，明确前后端依赖和真实功能验收。
- 没有文献 API 时，不把静态数据或模拟接口标记为已完成业务。
- 不扩展 PDF 阅读器、管理员或其他成员模块；不改变架构、主题及成员分工。
- 本会话到此停止；新会话按用户指令开始下一轮，按实际测试更新 tasks.md。
