# Litera

**科研文献智能管理与协作平台**，为《互联网软件开发技术与实践》课程小组项目，采用 OpenSpec 规约驱动开发。英文项目名称及 GitHub 仓库名称：`Litera`。

项目围绕文献管理、PDF 阅读、翻译、笔记、信息提取和 AI 问答组织六个模块，使用 Litera 自有品牌及北大红主题。

## 翻译与笔记：已验收，GitHub交付待确认（2026-10-26）

功能3/4及个人模型已在统一5183完成用户五项验收。包含手动/实时双向翻译、模型设置/安全存储、笔记M:N/自动保存/来源块/搜索/PDF跳页与精确高亮；AI回答保存目前为已验收的固定Mock适配，真实QA由06负责人提供。当前所有改动仍未提交/推送。

- [GitHub交付范围、测试与PR方案](docs/delivery/github-delivery.md)
- [Windows/Linux安全部署、主密钥和迁移](docs/delivery/deployment.md)
- [QA/提取与共享模型团队接口](docs/delivery/team-integration.md)
- [本地统一验收历史](docs/development/final-translation-notes-delivery.md)

0007/0008仅增量新增笔记及个人模型表，须联合备份/独立副本验证后由部署者执行；Windows保留DPAPI，Linux可配置独立主密钥文件AES-GCM，无明文回退。真实MySQL、Linux镜像构建及真实QA仍未执行，不与用户界面验收或Mock混淆。

## 工程规范

八类规范按老师顺序整理：[规范索引](docs/standards/README.md)。涵盖产品、后端、安全、测试、部署运维、AI应用、数据、评审与完成定义。长期入口为[AGENTS.md](AGENTS.md)，重复审查使用[规范审查技能](.agents/skills/litera-standards-review/SKILL.md)。

规范中的实现状态以本仓源码为准。翻译、笔记与个人模型模块目前仅在Litera-test副本实现，尚未合入本仓库；自动提取和AI问答仍待接入。

密钥泄露由部署实例持有人按[处置与轮换步骤](docs/standards/3-security.md#机密泄露处置与轮换)处理，不能只删除文件或重生成.env。适用测试/检查入口见[测试规范](docs/standards/4-testing.md)与[评审规范](docs/standards/8-review-specification.md#3-当前可用检查入口)，未合并的脚本不可直接照抄执行。

## 用户与场景

| 用户 | 场景 | 页面/实现边界 |
| --- | --- | --- |
| 访客 | 注册、登录 | /register、/login，两仓已有 |
| 普通用户 | 本人PDF管理、分类检索、手工题录、回收站 | /library，两仓已有 |
| 普通用户 | 阅读/搜索/批注/导出、资料/密码 | /reader/:documentId、/profile，两仓已有 |
| 普通用户 | 选区翻译、M:N笔记/来源定位、个人模型 | Litera-test阅读面板及/settings/ai；原Litera未合并 |

本期无管理员/跨用户共享；页面四状态、术语、交互约束见[产品规范](docs/standards/1-product.md)。模型未配置/环境未启用须明确提示。

## 功能范围

- **账号与文献管理**：注册/登录、个人资料与修改密码，PDF导入/原件下载、手工题录编辑、文件夹/标签、筛选检索、最近阅读和回收站。
- **PDF阅读与编辑**：三种阅读视图、缩放/搜索/选区、阅读进度、多标签、13类批注/形状/插入对象，以及带批注PDF导出。导出生成独立文件，保留原始PDF，不承诺第三方软件原生可编辑。
- **尚未接入本仓库**：翻译、笔记、个人模型、题录自动提取和AI问答；不支持OCR、加密PDF、跨用户共享及文件夹/批量导入。

具体交付状态、验收边界和历史问题见[开发交接](HANDOFF.md)及[开发记录](docs/development/2026-10-20-delivery.md)。

## Windows CMD 启动

### 首次启动

以下命令均使用Windows CMD，独立代码块默认从项目根目录执行。前置条件：Docker Desktop已运行且使用Linux容器；安装Python 3.12+用于生成本地配置。仅运行Compose页面不需要宿主机安装Node或MySQL。

在项目根目录执行：

```cmd
python scripts\init_env.py
docker compose up -d --build --wait
```

初始化脚本为 MySQL 与会话生成随机秘密，写入已被忽略的 `.env`，不会覆盖已有文件。首次构建会拉取缺失的基础镜像；后续修改代码后重新执行同一条 Compose 命令更新镜像和服务。API 启动时自动执行 `alembic upgrade head`，无需另建业务表。

访问 [登录页](http://localhost:8080/login) 或 [注册页](http://localhost:8080/register)，自行注册账号。注册成功后需要登录，没有预置演示账号。API 健康检查为 [health](http://localhost:8080/api/v1/health)，接口文档为 [API docs](http://localhost:8080/api/docs)。

### 后续启动与更新

若已有 .env 和数据库卷，无需重新生成配置。启动 Docker Desktop 后，在项目根目录下执行：

```cmd
docker compose up -d --build --wait
```

该命令适用于代码更新后的重新构建与启动。只启动已有镜像、没有代码或配置更新时，可用 `docker compose up -d --wait`。启动完成后访问[登录页](http://localhost:8080/login)。

### 查看日志与停止

查看状态/日志与停止服务：

```cmd
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 db
docker compose down
```

`down` 保留 MySQL 和 PDF 命名卷；`down -v` 会删除数据，请勿作为普通重启操作。

## 配置

`MAX_UPLOAD_BYTES`控制单篇上传上限（默认52428800，50 MiB），`PDF_STORAGE_ROOT`控制私有PDF根目录（Compose默认/data/pdfs）。可在已有.env手动追加配置，重建后生效，不需重新生成秘密。容器私有卷挂载路径跟随PDF_STORAGE_ROOT；更改路径前保持同一命名卷并备份。Nginx流式代理，API限制请求流和实际PDF大小，前端从GET /api/v1/library/config读取真实上限。

`.env.example` 提供非秘密默认值，`.env` 保存实际本地配置，不应提交。默认页面端口8080、会话24小时、密码8–128字符、注册/登录每IP合计20次/60秒；当前限流是单API进程内计数。

- `PUBLIC_ORIGIN` 必须与浏览器地址的协议、主机和端口完全一致；默认 `http://localhost:8080`，不加尾部斜线。使用 `127.0.0.1` 或其他端口访问时也须对应修改它。
- 改页面端口时同时改 `APP_PORT` 和 `PUBLIC_ORIGIN`。生产使用 HTTPS，并设置 `APP_ENV=production`、`COOKIE_SECURE=true`；当前Compose未内置生产HTTPS入口。
- `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`SESSION_SECRET` 由脚本生成；MySQL URL使用生成的十六进制密码。已有数据卷时不要直接改数据库密码，MySQL初始化变量不会替已有用户更换密码。
- `IMAGE_REGISTRY` 默认 `public.ecr.aws/docker/library`，使用 Docker Official Images 的公开ECR源；可改为 `docker.io/library`。项目不会修改全局Docker配置。
- MySQL和API仅在Compose网络内，Nginx为唯一对外入口。数据库卷为 `litera_mysql_data`。

## 测试

文献库和阅读器的独立浏览器测试无需Docker。先安装后端虚拟环境依赖、前端依赖和Chromium，再在frontend目录运行`npm run test:library`或`npm run test:reader`。套件使用8001临时SQLite API和5175 Vite，不修改开发数据库。认证UI使用5174，端口占用时可设置`set LITERA_UI_PORT=5176`。产物保存在frontend/test-results对应套件目录，截图不提交。

本地后端测试（独立临时SQLite库，走真实迁移，不触碰开发MySQL数据）：

```cmd
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
set TEST_DATABASE_URL=
.venv\Scripts\python -m pytest -q
```

MySQL版本测试由你在Compose服务启动后手动执行，使用独立 `litera_test` 数据库：

```cmd
docker compose exec -T api python -m pytest -q
```

测试会清理目标测试库中的数据，运行前须核对实例及数据库隔离；代码校验数据库名并拒绝非litera_test库。初次MySQL初始化会创建测试库；旧卷缺少测试库时见[测试库说明](docs/development/p2-b.md)。SQLite结果不能替代真实MySQL验证。

前端构建、基础测试与浏览器验收（需要 Node 24+；端到端测试需要已启动的服务）：

```cmd
cd frontend
npm ci
npm run build
npm test
npx playwright install chromium
npm run test:e2e
```

真实认证端到端测试（auth-integration）默认访问 `http://localhost:8080`，使用真实API并创建 `e2e-` 前缀验证账号。改变端口时先设置 `set LITERA_URL=http://localhost:新端口`。

## 可选：本地前端热更新

需要 Node 24+，后端仍由用户手动启动的 Compose 服务提供。先将 .env 的 PUBLIC_ORIGIN 改为 `http://localhost:5173`，随后在根目录下执行：

```cmd
docker compose up -d --build --wait
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

用 http://localhost:5173/login 访问，终端保持运行，Ctrl+C 停止。Vite 将 API 转发到8080；可通过 LITERA_API_PROXY 改代理目标。恢复8080页面时还原 PUBLIC_ORIGIN 并手动更新 API 服务。Cookie、CSRF 和 Origin 校验在开发模式同样启用。

## 技术方案与分工

采用 B/S 架构、前后端分离：Vue 3 + TypeScript + Element Plus，FastAPI + SQLAlchemy/Alembic，MySQL，Docker Compose + Nginx。PDF.js 6.4.299用于阅读；pypdf 6.20.1 + ReportLab 4.4.10用于带批注PDF导出。PyMuPDF仅供隔离开发渲染验证，LLM API + RAG属于后续规划。

| 成员 | 负责模块 |
| --- | --- |
| Jensen Zhang | 文献管理、PDF 阅读与文献编辑 |
| Siguo Liu | 文献翻译、文献笔记 |
| Jialu Ma | 文献信息自动提取、AI 文献智能问答 |

## 仓库与文档

`frontend/` 为前端，`backend/` 为认证、文献管理后端与迁移，`scripts/` 为本地配置/测试库初始化脚本，`docs/design/` 为总体设计，`docs/development/` 为阶段验收记录，`openspec/changes/` 为六模块规划。前后端依赖分别锁定于package-lock.json和requirements.txt。

- [新会话开发交接](HANDOFF.md)
- [六模块总览](openspec/changes/README.md)
- [设计文档索引](docs/design/README.md)
- [阶段开发与验收计划](docs/design/delivery-plan.md)
- [设计决策](docs/design/decisions.md)
- [规划校验记录](docs/design/validation.md)
