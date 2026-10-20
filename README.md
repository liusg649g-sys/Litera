# Litera

**科研文献智能管理与协作平台**，为《互联网软件开发技术与实践》课程小组项目，采用 OpenSpec 规约驱动开发。英文项目名称及 GitHub 仓库名称：`Litera`。

项目围绕文献管理、PDF 阅读、翻译、笔记、信息提取和 AI 问答组织六个模块，使用 Litera 自有品牌及北大红主题。

## 当前进度

本轮最终实现、各批实际测试、暂缓需求及Windows CMD手动GitHub上传步骤，统一见
[2026-10-20交付索引](docs/development/2026-10-20-delivery.md)。

- P3-C2：共享标签/批量关闭与草稿保护、每篇阅读及面板状态、ReaderContext/navigation adapter、长文和十标签资源验证。见[P3-C2](docs/development/p3-c2.md)与[公共接口](docs/design/reader-public-api.md)。
- 账号安全：个人资料页修改密码，成功撤销本人全部会话并重新登录。见[修改密码](docs/development/password-change.md)。
- 插入对象：水印/签名/图片角度滑块与数值输入同步，范围−90°～90°、1°步进；保存/撤销/导出一致，调角度时属性框固定。签名属性移除更换图片，图片仍保留。见[插入角度](docs/development/insert-rotation.md)。
- 选区快捷批注：**仅批注模式下选中文字后右键显示，不自动弹出**；上排五工具，下排常用色/自定义色；悬停保持、约50px距离淡出。见[快捷面板](docs/development/selection-quick-toolbar.md)。
- 移除资产管理/重新读取图片维护入口，后台自动回收与撤销租约保留；上传提示为“本地 PDF · 单篇上限 50.0 MB”，实际逐篇字节限制不变。见[图片入口精简](docs/development/reader-asset-ui.md)。

Change 02当前35/36（6.1–6.5完成；6.6文档已交付，最终用户实际功能/UI验收待确认），未正式结束。
自动生成目录、题录自动识别（Change 05）、文件夹/批量导入暂未实现；03–06未开发。
不同测试批次和SQLite/真实MySQL边界见交付索引，不把自动化或文档交付当作用户最终验收。

包含本会话全部代码的部署需用户手动同时更新API/nginx（密码和旋转均有后端变更）：

```cmd
docker compose up -d --build --no-deps --wait api nginx
```

随后Ctrl+F5；若相关API已经部署、仅更新后续前端交互，可只更新nginx。仅文档变化无需部署。
无新增迁移，head仍0006_reader_assets；不改原始PDF，不重建数据库或删除既有数据卷，不自动commit/push/sync/archive。

以下C1及A/B内容为历史已验收记录，与本轮分批自动化证据分开。

Change 01及Change 02 A1/A2/B1/B2/C1均已通过用户实际功能/UI验收，C1交付时为30/36；P3-C1已交付，支持全部13类对象的带批注PDF导出，保留原始PDF字节。导出以第三方可靠可见为目标，不增加附录页，注释正文写入原生PDF批注供查看，不承诺第三方原生可编辑。独立荧光笔已取消。

最新反馈修复：[注释双模式气泡与无附录导出](docs/development/p3-c1-comment-popup.md)。悬浮显示/移走消失，单击固定/外部点击关闭，淡入淡出各100ms；旧导出文件需重新导出。

阅读器新增[原生全屏模式](docs/development/reader-fullscreen.md)：批注列表与下载之间的按钮切换全屏，只将Litera品牌栏以200ms动画收起/展开；保留文献管理/文献标签，阅读和编辑工具栏正常占位，退出保留侧栏和草稿。本轮实际UI已获用户整体验收；浏览器原生Esc与任务栏表现仍由目标环境决定。

C1先完成技术验证/ADR，再实现expectedAnnotationRevision一致快照、受保护同步导出、隔离进程与资源清理。阅读器统一“下载PDF”下拉入口，分别提供“导出带批注PDF”和“下载原始PDF”，带批注文件名使用“原文件名_带批注.pdf”，未保存草稿需明确处理。窄屏批注侧栏也可导出，不丢失编辑草稿。

用户明确确认5.5在Google Chrome和Microsoft Edge测试，导出内容均正常显示；按该次确认范围完成5.1–5.6。Adobe Acrobat Reader未测试，浏览器具体版本未提供，不推定通过；03–06未实施，C2本轮状态见上文。真实MySQL专项不以SQLite代替。实现、13类矩阵、真实测试批次与手动验收见 [P3-C1记录](docs/development/p3-c1.md)，选型见 [ADR](docs/design/adr-0007-annotated-pdf-export.md)，历史B1/B2见 [HANDOFF](HANDOFF.md)。

C1新增运行依赖ReportLab/psutil与内置OFL中文字体，无新增迁移，head仍0006_reader_assets。首次部署这些实现需手动同时重建API/nginx并保留已有.env与数据卷；C1历史文档交接本身无需再次部署，包含本轮账号安全/旋转时按本节开头同时更新API/nginx。本轮未运行Docker、业务库迁移或提交/推送/归档。

以下Windows CMD默认从项目根目录开始，原有配置/首次启动方式继续有效。

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

采用 B/S 架构、前后端分离：Vue 3 + TypeScript + Element Plus，FastAPI + SQLAlchemy/Alembic，MySQL，Docker Compose + Nginx。PDF.js 6.4.299用于阅读；pypdf 6.20.1 + ReportLab 4.4.10用于C1导出。PyMuPDF仅供隔离开发渲染验证，LLM API + RAG属于后续规划。

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

Change 01及02 P3-A1/A2/B1/B2/C1均已通过实际验收；阶段历史分别见[P3-A2记录](docs/development/p3-a2.md)及[P3-B1记录](docs/development/p3-b1.md)。当前迁移链至0006_reader_assets，保留账号、文献、原PDF及独立进度。C2本轮交付等待用户实际功能/UI验收，不自动提交、推送或归档。管理员、跨用户共享等扩展另立change。

## P1 页面优化

登录/注册已优化为首次无错误、非空内容失焦校验、提交统一校验和修改后清除错误。品牌主色正式统一为#9B0000，Token集中于frontend/src/theme.css。浏览器测试分为auth-integration（8080真实服务）和auth-ui（本地Vite的UI隔离测试）；后者仅替身处理匿名会话与指定错误响应，不代表模拟业务实现。

仅验证最新UI、不启动Docker：在frontend目录运行 `npm run test:e2e -- --project=auth-ui`。Docker中的前端更新仍须用户手动执行项目根目录的 `docker compose up -d --build --wait`，然后刷新浏览器。

历史测试：P2-B后端SQLite73/73、完整真实HTTP文献库Playwright21/21、auth-ui10/10；最新标签布局修复构建通过、Vitest10/10及定向浏览器3/3，全量套件新增用例后未重跑。证据见[P2-B](docs/development/p2-b.md)和[P2-B UI](docs/development/p2-b-ui.md)。本次仅文档与关键接入代码核对，重新执行OpenSpec严格校验；未重跑业务测试，未执行Docker。

## P3-A1/A2历史验证

前端生产构建（含vue-tsc）通过、Vitest26/26；真实生产构建阅读器Playwright7/7加公开实际论文1/1、库回归22/22；后端pytest73/73。API/浏览器测试使用临时SQLite与私有PDF目录，不等同MySQL部署验收。无需Docker运行阅读器套件：frontend下`npm run test:reader`。手动重建仍使用上文`docker compose up -d --build --wait`，本轮未替用户执行。

P3-A1历史交互补充：库/阅读器共享标签、标题阅读/详情下载、阅读组默认收起二级栏、侧栏拖动与Tooltip优化，以及首帧后真实最近阅读记录。实现/证据与手动步骤见[A1交互记录](docs/development/p3-a1-ux.md)，不含A2/批注业务。

P3-A2历史UI补充将阅读器顶部压缩为48/40/40/40px，移除Footer，统一20px品牌/12px基础字号、SVG箭头与12px阅读间距，修复双页7px额外横向溢出；当时为12/36，后续B1完成并验收时18/36；本轮B2状态见开头。实现、前端测试及仅重建nginx的CMD验收步骤见[UI记录](docs/development/p3-a2-ux.md)。
