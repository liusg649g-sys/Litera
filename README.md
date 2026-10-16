# Litera

**科研文献智能管理与协作平台**，为《互联网软件开发技术与实践》课程小组项目，采用 OpenSpec 规约驱动开发。英文项目名称及 GitHub 仓库名称：`Litera`。

项目围绕文献管理、PDF 阅读、翻译、笔记、信息提取和 AI 问答组织六个模块，使用 Litera 自有品牌及北大红主题。

## 当前进度

Change 01及Change 02 P3-A1/A2/B1已通过用户实际功能及UI验收。**P3-B1于2026-10-16正式交付，Change 02当前18/36；下一阶段P3-B2（4.1–4.6）尚未启动。** 六类文本批注、CAS/幂等保存、补偿撤销重做、列表及文献生命周期已交付；注释在列表卡片内编辑，自由文本在PDF原位编辑/改框。最终功能、历次测试及遗留边界见[B1记录](docs/development/p3-b1.md)和[HANDOFF](HANDOFF.md)。03–06、手绘/形状/插入及带批注导出尚未实现，Change 02未归档。

产品调整（2026-10-16）：正式取消独立荧光笔及其工具栏占位。保留精确文本高亮与后续自由手绘，Change 02对象及导出目标统一为13类（B1六类文本批注+手绘+三形状+三插入）；B2 4.1仅开发手绘，目前尚未启动。现有六类API、数据和保存机制不变。

B1历次测试包含后端pytest123/123（SQLite）、前端单测50/50和阅读器全量32/32；最后局部修复另有定向测试，不能视为再次全量通过。用户Docker功能/UI验收已完成，真实MySQL专项集成仍无通过证据。B1验收文档收尾未重跑业务测试；取消荧光笔的本次前端检查见B1记录末节。

以下命令默认从项目根目录开始；进入frontend/backend的代码块应分别在根目录打开终端执行，文档不依赖某台电脑的绝对目录。

开发及测试详情见 [P1 验收记录](docs/development/p1-auth.md)。Docker 拉取、构建和启动由使用者手动执行，开发过程中不自动提交或推送代码。

P2-A历史记录见[P2-A记录](docs/development/p2-a.md)。服务启动时自动增量迁移至0005_annotations，保留已有账号、文献ID和PDF；不重建业务表。私有命名卷`litera_pdf_data`仅API挂载；不要用`down -v`删除数据。数据库和PDF卷需一起备份。

已验收的文献库布局沿用[P2-A UI记录](docs/development/p2-a-ui.md)：六列单行省略/浅色Tooltip、阅读/详情/更多菜单、右侧信息与编辑面板和局部草稿确认、右下角3秒通知（按B1最终反馈统一）。P2-B仅补充真实分类、筛选、历史及回收站交互，参考06–13截图。

P2-B局部交互优化见[本轮UI记录](docs/development/p2-b-ui.md)：独立快捷移动/标签窗口、统一Element Plus下拉、300ms即时检索和真实上下文空状态；未改后端或数据库，完整分类编辑与既有生命周期保留。

## Windows CMD 启动

### 首次启动（由使用者手动执行）

前置条件：Docker Desktop 已运行且使用 Linux 容器；安装 Python 3.12+（生成本地配置用）。仅运行 Compose 页面时不需要宿主机安装 Node 或 MySQL。

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

该命令适用于代码更新后的重新构建与启动。只启动已有镜像、没有代码或配置更新时，可用 `docker compose up -d --wait`。启动完成后访问 http://localhost:8080/login。

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

P2-A增加`MAX_UPLOAD_BYTES`（默认52428800，50 MiB）与`PDF_STORAGE_ROOT`（Compose默认/data/pdfs）。可在已有.env手动追加配置，重建后生效，不需重新生成秘密。容器私有卷挂载路径跟随PDF_STORAGE_ROOT；更改路径前保持同一命名卷并备份。Nginx流式代理，API限制请求流和实际PDF大小，前端从GET /api/v1/library/config读取真实上限。

`.env.example` 提供非秘密默认值，`.env` 保存实际本地配置，不应提交。默认页面端口8080、会话24小时、密码8–128字符、注册/登录每IP合计20次/60秒；当前限流是单API进程内计数。

- `PUBLIC_ORIGIN` 必须与浏览器地址的协议、主机和端口完全一致；默认 `http://localhost:8080`，不加尾部斜线。使用 `127.0.0.1` 或其他端口访问时也须对应修改它。
- 改页面端口时同时改 `APP_PORT` 和 `PUBLIC_ORIGIN`。生产使用 HTTPS，并设置 `APP_ENV=production`、`COOKIE_SECURE=true`；本轮未交付生产HTTPS配置。
- `MYSQL_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`SESSION_SECRET` 由脚本生成；MySQL URL使用生成的十六进制密码。已有数据卷时不要直接改数据库密码，MySQL初始化变量不会替已有用户更换密码。
- `IMAGE_REGISTRY` 默认 `public.ecr.aws/docker/library`，使用 Docker Official Images 的公开ECR源；可改为 `docker.io/library`。项目不会修改全局Docker配置。
- MySQL和API仅在Compose网络内，Nginx为唯一对外入口。数据库卷为 `litera_mysql_data`。

## 测试

无需Docker的P2-A/P2-B真实浏览器测试（先安装backend/.venv依赖和frontend依赖及Chromium）：在frontend目录运行`npm run test:library`，自动启动127.0.0.1:8001临时SQLite API与5175 Vite，完成后停止；不使用模拟文献成功数据，不修改开发数据库。测试配置目前按Windows项目路径运行。认证UI默认5174，端口占用可先`set LITERA_UI_PORT=5176`。测试产物分别存test-results/library和test-results/auth；截图不提交。

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

测试代码校验数据库名并拒绝对非测试MySQL库清理数据。初次MySQL初始化会创建测试库；旧卷缺少测试库时见[P2-B记录](docs/development/p2-b.md)。用户功能/UI验收已通过；本次文档收尾未执行Docker/MySQL测试，也未收到专项pytest日志，不能将历史SQLite或P1结果当作最新MySQL测试证据。

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

采用 B/S 架构、前后端分离：Vue 3 + TypeScript + Element Plus，FastAPI + SQLAlchemy/Alembic，MySQL，Docker Compose + Nginx。PDF.js 6.4.299已用于P3-A1；PyMuPDF、LLM API + RAG仍属于后续规划技术。

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

Change 01及02 P3-A1/A2/B1均已通过实际验收；阶段历史分别见[P3-A2记录](docs/development/p3-a2.md)及[P3-B1记录](docs/development/p3-b1.md)。当前迁移链至0005_annotations，保留账号、文献、原PDF及独立进度。下一阶段为P3-B2（4.1–4.6），尚未启动；须另行授权，不自动开发、提交、推送或归档。管理员、跨用户共享等扩展另立change。

## P1 页面优化

登录/注册已优化为首次无错误、非空内容失焦校验、提交统一校验和修改后清除错误。品牌主色正式统一为#9B0000，Token集中于frontend/src/theme.css。浏览器测试分为auth-integration（8080真实服务）和auth-ui（本地Vite的UI隔离测试）；后者仅替身处理匿名会话与指定错误响应，不代表模拟业务实现。

仅验证最新UI、不启动Docker：在frontend目录运行 `npm run test:e2e -- --project=auth-ui`。Docker中的前端更新仍须用户手动执行项目根目录的 `docker compose up -d --build --wait`，然后刷新浏览器。

历史测试：P2-B后端SQLite73/73、完整真实HTTP文献库Playwright21/21、auth-ui10/10；最新标签布局修复构建通过、Vitest10/10及定向浏览器3/3，全量套件新增用例后未重跑。证据见[P2-B](docs/development/p2-b.md)和[P2-B UI](docs/development/p2-b-ui.md)。本次仅文档与关键接入代码核对，重新执行OpenSpec严格校验；未重跑业务测试，未执行Docker。

## P3-A1/A2历史验证

前端生产构建（含vue-tsc）通过、Vitest26/26；真实生产构建阅读器Playwright7/7加公开实际论文1/1、库回归22/22；后端pytest73/73。API/浏览器测试使用临时SQLite与私有PDF目录，不等同MySQL部署验收。无需Docker运行阅读器套件：frontend下`npm run test:reader`。手动重建仍使用上文`docker compose up -d --build --wait`，本轮未替用户执行。

P3-A1历史交互补充：库/阅读器共享标签、标题阅读/详情下载、阅读组默认收起二级栏、侧栏拖动与Tooltip优化，以及首帧后真实最近阅读记录。实现/证据与手动步骤见[A1交互记录](docs/development/p3-a1-ux.md)，不含A2/批注业务。

P3-A2历史UI补充将阅读器顶部压缩为48/40/40/40px，移除Footer，统一20px品牌/12px基础字号、SVG箭头与12px阅读间距，修复双页7px额外横向溢出；当时为12/36，后续B1已完成并验收，当前18/36。实现、前端测试及仅重建nginx的CMD验收步骤见[UI记录](docs/development/p3-a2-ux.md)。
