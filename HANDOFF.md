# Litera 开发交接

更新时间：2026-10-15。项目根目录：D:\PKU\Projects\Litera。

## 当前停止点

Change 01（P1/P2-A/P2-B及UI优化）已完成开发，用户已明确确认实际功能和UI验收通过。
本次仅文档收尾、规约核对和02关键依赖检查；没有开发阅读器，没有改业务代码/数据库/Compose。
下一会话先读本文件、[README](README.md)、[设计索引](docs/design/README.md)及[02设计](openspec/changes/02-pdf-reader/design.md)。
专项MySQL自动化日志未在本次提供，不能把历史SQLite结果写成MySQL通过。
01任务33/34：5.B1沿用用户勾选；5.A1仅剩专项MySQL补证，功能/UI验收不再待执行。
01尚未同步为主规格或归档；本次不archive，后续须用户明确指令并核对剩余证据项。

## 架构与运行

- B/S：Vue 3 + TypeScript + Element Plus；FastAPI + SQLAlchemy/Alembic；MySQL 8.4；Compose三服务。
- Nginx为同源唯一入口，前端固定/api/v1；API/数据库在内网，PDF私有卷仅API挂载。
- 前端依赖锁于frontend/package-lock.json；后端锁于backend/requirements.txt；宿主开发Node 24+、Python 3.12。
- 当前迁移链0001_auth → 0002_documents → 0003_library，API启动自动alembic upgrade head。
- 增量升级保留用户、documentId、题录和PDF存储键，不重建已有业务表。
- 默认上传50 MiB（MAX_UPLOAD_BYTES=52428800），PDF_STORAGE_ROOT容器默认/data/pdfs。
- .env由scripts/init_env.py生成且不覆盖已有文件；不要提交会话/数据库秘密。
- APP_PORT与PUBLIC_ORIGIN同时调整；Origin必须与浏览器协议/主机/端口一致；生产HTTPS设置Secure。
- MySQL/PDF命名卷为litera_mysql_data、litera_pdf_data；联合备份，禁止用down -v普通重启。
- Windows CMD完整配置/运行说明见[README](README.md)，本次未运行Docker。

用户手动重新构建（已有.env无需再次初始化）：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
docker compose ps
```

默认页面http://localhost:8080/login，健康检查/api/v1/health，接口文档/api/docs。
本地Vite通过LITERA_API_PROXY代理API，默认8080；热更新时PUBLIC_ORIGIN须对应5173。

## 六个 change 状态

| Change / 负责人 | 状态 |
| --- | --- |
| 01-literature-management / Jensen Zhang | 功能及UI已验收；33/34，专项MySQL补证；未归档 |
| 02-pdf-reader / Jensen Zhang | 规划完成，0/12；下次按P3-A/B/C实施 |
| 03-translation / Siguo Liu | 规划完成，0/6；未实现 |
| 04-literature-notes / Siguo Liu | 规划完成，0/6；未实现 |
| 05-metadata-extraction / Jialu Ma | 规划完成，0/7；未实现 |
| 06-ai-qa / Jialu Ma | 规划完成，0/8；未实现 |

六个change均有proposal/design/specs/tasks；artifact done只表示规划文档齐全。
主规格openspec/specs仍为空。范围与负责人见[六模块总览](openspec/changes/README.md)。

## Change 01 已实现与验收

- P1：注册/登录/退出、会话恢复、个人资料、Argon2id、Cookie/Origin/CSRF、错误包络及用户隔离。
- P2-A：真实PDF上传、结构/限额校验、用户内SHA-256重复含回收站、私有存储、失败补偿。
- 文献列表/排序/分页、详情和手工题录CAS编辑、浏览器PDF预览、原文件下载、单Range。
- P2-B：个人单层文件夹、多标签CRUD/关联、删除分类保留文献、组合元数据检索、真实最近打开。
- 生命周期：软删除、原ID恢复、二次确认永久删除、持久清理状态查询/显式重试；202不能当成功。
- 永久清理开始后不可恢复；成功保留作业审计、移除文献/文件/当前关联，允许相同PDF重新上传。
- 白灰/#9B0000主题、52px品牌栏；侧栏240px默认、180–320px可调、折叠56px。
- 六列单行省略/浅色Tooltip、阅读/详情/更多、右下角5秒通知和真实空状态。
- 信息面板默认360px、320–520px可调，中央不足空间改覆盖抽屉；未保存确认局部88%居中。
- 快捷移动/管理标签独立窗口；完整面板仍可编辑分类，保存与列表同步；失败保留输入。
- 面板标签纵向32px/项、上限200px滚动、长名称省略Tooltip；独立标签快捷窗口保持原布局。
- Element Plus下拉统一；关键词300ms防抖、旧请求保护、分页复位，清空不丢其他筛选。
- 本地上传、分类、检索、最近阅读和回收站均真实API/数据库；无模拟成功业务数据。
- 仍是浏览器预览；/reader/:documentId仅保留稳定入口并跳回详情，不代表在线阅读器完成。

详细历史：[P1](docs/development/p1-auth.md)、[P2-A](docs/development/p2-a.md)、[P2-A UI](docs/development/p2-a-ui.md)、[P2-B](docs/development/p2-b.md)、[P2-B UI](docs/development/p2-b-ui.md)。

## 可直接复用的代码与接口

- frontend/src/auth.ts、api.ts、main.ts：会话/CSRF/401失效事件；router.ts：路由恢复与认证守卫。
- frontend/src/library.ts：DocumentDTO、文献读写、contentUrl、recordOpen；LibraryPage.vue保留导航和上传。
- components/DocumentInfoPanel.vue：真实题录/分类表单及草稿保护；OverflowText.vue：统一溢出Tooltip。
- components/LibraryActionDialog.vue、DocumentClassifyDialog.vue：局部尺寸操作窗；theme.css/library.css：主题与布局。
- backend/app/main.py：current_session/require_csrf；documents.py：owner有效文献、DTO、题录CAS及内容流。
- backend/app/library.py：分类、组合查询、progress/history和清理作业；models.py：现有实体。
- GET/PATCH /api/v1/documents/{id}复用题录version；content?download=true用于下载。
- GET/PUT /documents/{id}/progress复用阅读记录；PUT {}写lastReadAt并递增独立progress.version。
- GET /reading-history固定最近打开倒序；列表/下载/GET内容不更新阅读记录。
- documents/document_files/folders/tags/document_tags/reading_progress/cleanup_jobs已建；annotations尚未建。
- 公开DTO无ownerId/storageKey，嵌套ID仍校验归属；他人/已删除文献404，写请求需要Origin/CSRF。
- API、模型和扩展契约见[API](docs/design/api-contracts.md)、[模型](docs/design/data-model.md)、[模块边界](docs/design/module-dependencies.md)。

## 测试证据与未解决事项

- 历史P2-B后端pytest：临时SQLite73/73，真实迁移/API/文件；不是MySQL集成验收。
- 历史完整文献库Playwright：真实HTTP/SQLite/PDF/Vite 21/21；认证UI 10/10。
- 最新标签布局：vue-tsc/Vite构建通过，Vitest10/10，定向真实浏览器3/3。
- 新增标签布局用例后未重跑完整22项浏览器套件，不能写全量22/22；记录见P2-B UI。
- 本次OpenSpec 1.14.1严格校验6/6；24份Markdown、86个本地链接检查均通过，未重跑业务测试。
- 用户功能/UI验收已通过；专项MySQL pytest及最新部署auth-integration日志未提供。
- MySQL独立测试命令：根目录docker compose exec -T api python -m pytest -q，由用户执行。
- 仅允许litera_test测试库；旧卷缺测试库按scripts/mysql-init.sql及P2-B说明处理，不清理业务库。
- 专门旧版本升级自动化样例仍为SQLite；真实MySQL旧数据升级需额外核对，不把pytest总数等同升级证据。
- 文献库浏览器测试：frontend下npm run test:library，临时API8001/Vite5175，不触碰开发数据。
- auth-ui使用5174，可set LITERA_UI_PORT=5176；auth-integration默认8080，LITERA_URL可覆盖。
- 打开网页本身不会停止Vite；服务连接拒绝属于测试基础设施失败，不能计为通过。
- 已知边界：上传进程硬退出可能留未引用文件，无自动扫描；清理失败仅显式重试。
- 当前预览先写打开时间再导航PDF，记录的是发起打开，不能证明PDF成功渲染；02需明确记录时机。
- 历史Starlette/httpx弃用与Node颜色变量警告保留，本次不修复。
- 归档：功能/UI已满足用户验收，完整任务闭合尚待5.A1补证；严格校验不能替代专项测试。

## Change 02 接入注意事项

- 先替换reader占位跳转为受保护视图，再把文献库“阅读”接入；下载保留现有独立行为。
- 锁定pdfjs-dist及匹配worker并由Vite打包；当前没有PDF.js依赖或阅读器组件。
- PDF.js使用同源content URL复用HttpOnly Cookie；GET无需CSRF，progress/annotations写入沿用CSRF。
- 内容支持200/单Range206，含Accept-Ranges/Content-Length/Content-Range；非法/多Range416。
- 没有HEAD、ETag/If-Range专用实现；不要求不存在的缓存协商，不能用JSON api<T>解析PDF字节。
- PDF.js适配401/404/416及损坏文件；401接现有失效事件，离开/切换取消loadingTask并销毁实例。
- pageCount当前null；非null页码/缩放PUT当前503；02用轻量结构校验真实总页数，独立于05。
- progress复用原表，page_number为nullable整数、zoom为nullable字符串且DTO转float；新增写入明确范围/转换。
- annotations按既有契约增量迁移，owner/document/物理1-based页码、类型、选区、内容、颜色及CAS版本。
- 高亮/下划线存未旋转页面归一化多页矩形；书签可页级，批注可页/选区级；不改PDF原字节。
- 新关联须接入软删除屏蔽、恢复和永久清理/失败重试；过期或删除中的已开文献不可继续读取。
- ReaderContext/SelectionPosition/NoteDraft/Citation只有文档定义，须落地公共类型与事件，不能假定代码已存在。
- contextRevision与题录/进度/标注version分别管理；切换以documentId+contextRevision拒绝旧响应。
- context/selection事件供03/04/06接入；save-note和citation-navigate受真实模块就绪/权限/引用版本约束。
- 03–06未实现时禁用/说明业务入口，不伪造译文、笔记、提取、AI；02不负责供应商调用。
- 缩放范围/保存节流、PDF.js版本、面板初始尺寸与样本文献在实施时确定；详见[02设计](openspec/changes/02-pdf-reader/design.md)。

## 下一阶段顺序与协作限制

1. P3-A / tasks 1.x：PDF.js真实加载、翻页/缩放/目录/全文搜索/文本层、基础选区上下文。
2. P3-B / tasks 2.x：标注增量迁移/API/CAS、坐标覆盖层、高亮/下划线/书签/批注、阅读进度。
3. P3-C / tasks 3.x：多文献标签、左右面板/功能注册、公共事件与成员接入、真实端到端验收。

每阶段同步测试/契约，交付后等待验收；本次没有启动任何02实现任务。
保留既有未提交及已暂存改动；不reset/覆盖其他成员代码，不自动commit/push或新建分支。
迁移编号串行协调；公共DTO/事件/API变更列出生产者和消费者，避免各成员复制不同契约。
Docker构建/启动由用户手动执行，不改全局设置、不删数据卷、不替用户运行数据库升级。
未经明确要求不archive、不自动开始02或其他模块；本次完成后停止，下一会话获指令后继续。
