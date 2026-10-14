# Litera

**科研文献智能管理与协作平台**，为《互联网软件开发技术与实践》课程小组项目，采用 OpenSpec 规约驱动开发。英文项目名称及 GitHub 仓库名称：`Litera`。

项目围绕文献管理、PDF 阅读、翻译、笔记、信息提取和 AI 问答组织六个模块，使用 Litera 自有品牌及北大红主题。

## 当前进度

第一轮 P1 已实现普通用户注册、登录、退出、会话维护和个人资料。登录成功进入 `/library`，该页仅显示“文献库正在准备中”。01-literature-management 的 P1 任务已完成；文献管理业务、PDF 阅读和03–06模块仍待实现。本轮没有管理员端。

开发及测试详情见 [P1 验收记录](docs/development/p1-auth.md)。Docker 拉取、构建和启动由使用者手动执行，开发过程中不自动提交或推送代码。

## Windows CMD 启动

### 首次启动（由使用者手动执行）

前置条件：Docker Desktop 已运行且使用 Linux 容器；安装 Python 3.12+（生成本地配置用）。仅运行 Compose 页面时不需要宿主机安装 Node 或 MySQL。

在项目根目录执行：

```cmd
cd /d D:\PKU\Projects\Litera
python scripts\init_env.py
docker compose up -d --build --wait
```

初始化脚本为 MySQL 与会话生成随机秘密，写入已被忽略的 `.env`，不会覆盖已有文件。首次构建会拉取缺失的基础镜像；后续修改代码后重新执行同一条 Compose 命令更新镜像和服务。API 启动时自动执行 `alembic upgrade head`，无需另建业务表。

访问 [登录页](http://localhost:8080/login) 或 [注册页](http://localhost:8080/register)，自行注册账号。注册成功后需要登录，没有预置演示账号。API 健康检查为 [health](http://localhost:8080/api/v1/health)，接口文档为 [API docs](http://localhost:8080/api/docs)。

### 后续启动与更新

若已有 .env 和数据库卷，无需重新生成配置。启动 Docker Desktop 后，在 CMD 执行：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
```

该命令适用于代码更新后的重新构建与启动。只启动已有镜像、没有代码或配置更新时，可用 `docker compose up -d --wait`。启动完成后访问 http://localhost:8080/login。

### 查看日志与停止

查看状态/日志与停止服务：

```cmd
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 db
docker compose down
```

`down` 保留 MySQL 命名卷及注册数据；`down -v` 会删除数据，请勿作为普通重启操作。

## 配置

`.env.example` 提供非秘密默认值，`.env` 保存实际本地配置，不应提交。默认页面端口8080、会话24小时、密码8–128字符、注册/登录每IP合计20次/60秒；当前限流是单API进程内计数。

- `PUBLIC_ORIGIN` 必须与浏览器地址的协议、主机和端口完全一致；默认 `http://localhost:8080`，不加尾部斜线。使用 `127.0.0.1` 或其他端口访问时也须对应修改它。
- 改页面端口时同时改 `APP_PORT` 和 `PUBLIC_ORIGIN`。生产使用 HTTPS，并设置 `APP_ENV=production`、`COOKIE_SECURE=true`；本轮未交付生产HTTPS配置。
- `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`SESSION_SECRET` 由脚本生成；MySQL URL使用生成的十六进制密码。已有数据卷时不要直接改数据库密码，MySQL初始化变量不会替已有用户更换密码。
- `IMAGE_REGISTRY` 默认 `public.ecr.aws/docker/library`，使用 Docker Official Images 的公开ECR源；可改为 `docker.io/library`。项目不会修改全局Docker配置。
- MySQL和API仅在Compose网络内，Nginx为唯一对外入口。数据库卷为 `litera_mysql_data`。

## 测试

本地后端测试（独立临时SQLite库，走真实迁移，不触碰开发MySQL数据）：

```cmd
cd /d D:\PKU\Projects\Litera\backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest -q
```

MySQL版本测试由你在Compose服务启动后手动执行，使用独立 `litera_test` 数据库：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose exec -T api python -m pytest -q
```

测试代码校验数据库名并拒绝对非测试MySQL库清理数据。初次MySQL初始化会创建测试库；本轮该命令已验证22项通过，使用独立测试库。

前端构建、基础测试与浏览器验收（需要 Node 24+；端到端测试需要已启动的服务）：

```cmd
cd /d D:\PKU\Projects\Litera\frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

真实认证端到端测试（auth-integration）默认访问 `http://localhost:8080`，使用真实API并创建 `e2e-` 前缀验证账号。改变端口时先设置 `set LITERA_URL=http://localhost:新端口`。

## 可选：本地前端热更新

需要 Node 24+，后端仍由用户手动启动的 Compose 服务提供。先将 .env 的 PUBLIC_ORIGIN 改为 `http://localhost:5173`，随后在 CMD 执行：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

用 http://localhost:5173/login 访问，终端保持运行，Ctrl+C 停止。Vite 将 API 转发到8080；可通过 LITERA_API_PROXY 改代理目标。恢复8080页面时还原 PUBLIC_ORIGIN 并手动更新 API 服务。Cookie、CSRF 和 Origin 校验在开发模式同样启用。

## 技术方案与分工

采用 B/S 架构、前后端分离：Vue 3 + TypeScript + Element Plus，FastAPI + SQLAlchemy/Alembic，MySQL，Docker Compose + Nginx。PDF.js、PyMuPDF、LLM API + RAG属于后续模块的规划技术。

| 成员 | 负责模块 |
| --- | --- |
| Jensen Zhang | 文献管理、PDF 阅读与文献编辑 |
| Siguo Liu | 文献翻译、文献笔记 |
| Jialu Ma | 文献信息自动提取、AI 文献智能问答 |

## 仓库与文档

`frontend/` 为前端，`backend/` 为认证后端与迁移，`scripts/` 为本地配置/测试库初始化脚本，`docs/design/` 为总体设计，`docs/development/` 为阶段验收记录，`openspec/changes/` 为六模块规划。前后端依赖分别锁定于package-lock.json和requirements.txt。

- [新会话开发交接](HANDOFF.md)
- [六模块总览](openspec/changes/README.md)
- [设计文档索引](docs/design/README.md)
- [阶段开发与验收计划](docs/design/delivery-plan.md)
- [设计决策](docs/design/decisions.md)
- [规划校验记录](docs/design/validation.md)

后续按注册登录 → 文献库 → PDF 阅读器逐阶段推进。下一轮任务为“文献库主界面开发”，本次未开始；新会话按用户指令启动。管理员、跨用户共享等扩展另立change。

## P1 页面优化

登录/注册已优化为首次无错误、非空内容失焦校验、提交统一校验和修改后清除错误。品牌主色正式统一为#9B0000，Token集中于frontend/src/theme.css。浏览器测试分为auth-integration（8080真实服务）和auth-ui（本地Vite的UI隔离测试）；后者仅替身处理匿名会话与指定错误响应，不代表模拟业务实现。

仅验证最新UI、不启动Docker：在frontend目录运行 `npm run test:e2e -- --project=auth-ui`。Docker中的前端更新仍须用户手动执行项目根目录的 `docker compose up -d --build --wait`，然后刷新浏览器。

本轮UI修改和测试证据见 [P1 UI验收](docs/development/p1-ui.md)。最近前端构建通过，Vitest 7项、auth-ui 10项通过；六个OpenSpec严格校验通过。用户已认可注册页、文献库占位页和个人资料页；当前登录布局已完成修复，下一轮文献库业务尚未开始。
