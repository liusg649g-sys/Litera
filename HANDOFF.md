# Litera 开发交接

更新时间：2026-10-16。路径基准：项目根目录。

## 当前停止点

2026-10-16大纲体验修复：PdfOutline默认全部折叠，点击箭头按需逐层展开，标题跳页保持不变；切文献/大纲数据重置展开状态。类型/生产构建及真实PDF导航定向1/1通过，详见A2 UI记录末节；无后端/数据库变化，该修复已通过用户实际验收。随后用户确认B2整体验收完成，当前24/36；本轮仅同步文档，不需再次部署。

2026-10-16用户实际体验反馈：B2七类新增对象（手绘、矩形、圆形、椭圆、签名、水印、图片）的橡皮擦删除已局部修复。根因是drawing-overlay仅在空工具的选择状态开启命中，erase状态关闭了对象指针事件；新增独立erasing状态，只接收对象删除点击、不启用拖动/控制点，阅读组继续穿透。列表/工具栏/Delete键原已接通用删除。新增逐类四入口删除及补偿undo/redo回归，类型/生产构建及真实PDF定向4/4（2+2）、OpenSpec严格6/6通过；测试边界见B2记录末节。保存队列、后端及数据库未改。该修复后的B2整体已获用户验收，当前24/36；不进入C1/C2。

2026-10-16：P3-B2开发及实际体验反馈修复完成，用户已明确确认整体功能/UI验收通过，正式交付。Change 01及02 A1/A2/B1已验收状态保留。B2实现手绘/三形状/视觉签名/当前页水印/本地图片及资产管理，共13类；无独立荧光笔、手动页面旋转或证书签署。C1/C2与03–06未实施，不自动推进。

新对象采用页面实时绘制/放置、就近属性栏、✓保存/×取消；阅读模式穿透文本并只联动列表，对应工具组才显示编辑控制点。复用B1串行CAS/commandId、失败草稿、冲突备份、真实补偿撤销重做；原六类文本交互保留。完整实现、测试批次、限额、失败恢复与Windows CMD说明见 [P3-B2记录](docs/development/p3-b2.md)。Change 02当前24/36，tasks 4.1–4.6已勾选；用户实际验收依据为本会话的明确确认，自动化结果仍按实际批次记录。下一阶段P3-C1（5.1–5.6）尚未启动。

新增0006_reader_assets与Pillow==12.0.0；图片受保护上传/真实解码/归属校验/读取/清理，台账先于写文件，未引用1小时、删除对象后24小时租约，启动及每60秒扫描。清理失败可从插入组资产管理重试，永久删除纳入原cleanup_jobs。仅新增表，不重建旧业务表。开发测试使用独立临时SQLite，不操作用户业务MySQL/PDF。

本轮未运行Docker Compose、业务库迁移、Git commit/push、reset/clean或OpenSpec archive。用户需手动同时重建API/nginx，已有.env与命名卷保留；命令见下文。真实MySQL专项pytest及旧数据升级专项仍无通过证据。B1历史测试见 [P3-B1记录](docs/development/p3-b1.md)，不冒充本轮重跑结果。

本轮有效校验：后端148/148（临时SQLite）、Vitest55/55、阅读器38个不同用例分批通过，最末Esc补充后另定向2/2；文献库核心8/8，类型/生产构建及OpenSpec严格6/6通过。一次全量批次及若干基础设施失败不计通过，详见B2记录，不能称末次源码单批全量38/38。原ReaderPage约540kB chunk提示非阻断。

## 架构与运行

- B/S：Vue 3 + TypeScript + Element Plus；FastAPI + SQLAlchemy/Alembic；MySQL 8.4；Compose三服务。
- Nginx为同源唯一入口，前端固定/api/v1；API/数据库在内网，PDF私有卷仅API挂载。
- 前端依赖锁于frontend/package-lock.json；后端锁于backend/requirements.txt；宿主开发Node 24+、Python 3.12。
- 当前迁移链0001_auth → 0002_documents → 0003_library → 0004_reader_progress → 0005_annotations → 0006_reader_assets，API启动自动alembic upgrade head。
- 增量升级保留用户、documentId、题录和PDF存储键，不重建已有业务表。
- 默认上传50 MiB（MAX_UPLOAD_BYTES=52428800），PDF_STORAGE_ROOT容器默认/data/pdfs。
- .env由scripts/init_env.py生成且不覆盖已有文件；不要提交会话/数据库秘密。
- APP_PORT与PUBLIC_ORIGIN同时调整；Origin必须与浏览器协议/主机/端口一致；生产HTTPS设置Secure。
- MySQL/PDF命名卷为litera_mysql_data、litera_pdf_data；联合备份，禁止用down -v普通重启。
- Windows CMD完整配置/运行说明见[README](README.md)，本次未运行Docker。

用户手动重新构建（已有.env无需再次初始化）：

```cmd
rem 在项目根目录执行
docker compose up -d --build --wait
docker compose ps
```

默认页面http://localhost:8080/login，健康检查/api/v1/health，接口文档/api/docs。
本地Vite通过LITERA_API_PROXY代理API，默认8080；热更新时PUBLIC_ORIGIN须对应5173。

## 六个 change 状态

| Change / 负责人 | 状态 |
| --- | --- |
| 01-literature-management / Jensen Zhang | 功能及UI已验收；33/34，专项MySQL补证；未归档 |
| 02-pdf-reader / Jensen Zhang | P3-A1/A2/B1/B2已验收；24/36，C1尚未启动 |
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
- 六列单行省略/浅色Tooltip、阅读/详情/更多、右下角3秒通知（按B1最终反馈统一）和真实空状态。
- 信息面板默认360px、320–520px可调，中央不足空间改覆盖抽屉；未保存确认局部88%居中。
- 快捷移动/管理标签独立窗口；完整面板仍可编辑分类，保存与列表同步；失败保留输入。
- 面板标签纵向32px/项、上限200px滚动、长名称省略Tooltip；独立标签快捷窗口保持原布局。
- Element Plus下拉统一；关键词300ms防抖、旧请求保护、分页复位，清空不丢其他筛选。
- 本地上传、分类、检索、最近阅读和回收站均真实API/数据库；无模拟成功业务数据。
- 01交付时为浏览器预览/占位路由；本轮已由02 A1替换为真实PDF.js阅读器，保留独立原件下载。

详细历史：[P1](docs/development/p1-auth.md)、[P2-A](docs/development/p2-a.md)、[P2-A UI](docs/development/p2-a-ui.md)、[P2-B](docs/development/p2-b.md)、[P2-B UI](docs/development/p2-b-ui.md)。

## 可直接复用的代码与接口

- frontend/src/auth.ts、api.ts、main.ts：会话/CSRF/401失效事件；router.ts：路由恢复与认证守卫。
- frontend/src/library.ts：DocumentDTO、文献读写、contentUrl、recordOpen；LibraryPage.vue保留导航和上传。
- components/DocumentInfoPanel.vue：真实题录/分类表单及草稿保护；OverflowText.vue：统一溢出Tooltip。
- components/LibraryActionDialog.vue、DocumentClassifyDialog.vue：局部尺寸操作窗；theme.css/library.css：主题与布局。
- backend/app/main.py：current_session/require_csrf；documents.py：owner有效文献、DTO、题录CAS及内容流。
- backend/app/library.py：分类、组合查询、progress/history和清理作业；models.py：现有实体。
- GET/PATCH /api/v1/documents/{id}复用题录version；content?download=true用于下载。
- GET/PUT /documents/{id}/progress复用阅读记录；PUT {}兼容旧打开事件；A2扩展页码/倍率/模式及独立progress.version CAS，详见API契约。
- GET /reading-history固定最近打开倒序；列表/下载/GET内容不更新阅读记录。
- documents/document_files/folders/tags/document_tags/reading_progress/cleanup_jobs已建；B1已新增annotations/document_reader_state/annotation_command_receipts。
- 公开DTO无ownerId/storageKey，嵌套ID仍校验归属；他人/已删除文献404，写请求需要Origin/CSRF。
- API、模型和扩展契约见[API](docs/design/api-contracts.md)、[模型](docs/design/data-model.md)、[模块边界](docs/design/module-dependencies.md)。

## 测试证据与未解决事项

- 历史P2-B后端pytest：临时SQLite73/73，真实迁移/API/文件；不是MySQL集成验收。
- 历史完整文献库Playwright：真实HTTP/SQLite/PDF/Vite 21/21；认证UI 10/10。
- 历史P2-B标签布局：vue-tsc/Vite构建通过，Vitest10/10，定向真实浏览器3/3。
- 历史标签布局交付时新增用例后未重跑完整22项浏览器套件，不能写全量22/22；记录见P2-B UI。
- 前次文档收尾OpenSpec 1.14.1严格校验6/6、24份Markdown/86个本地链接通过；属于历史记录。当时结果见docs/design/validation.md；本轮B1测试见docs/development/p3-b1.md。
- 用户功能/UI验收已通过；专项MySQL pytest及最新部署auth-integration日志未提供。
- MySQL独立测试命令：根目录docker compose exec -T api python -m pytest -q，由用户执行。
- 仅允许litera_test测试库；旧卷缺测试库按scripts/mysql-init.sql及P2-B说明处理，不清理业务库。
- 专门旧版本升级自动化样例仍为SQLite；真实MySQL旧数据升级需额外核对，不把pytest总数等同升级证据。
- 文献库浏览器测试：frontend下npm run test:library，临时API8001/Vite5175，不触碰开发数据。
- auth-ui使用5174，可set LITERA_UI_PORT=5176；auth-integration默认8080，LITERA_URL可覆盖。
- 打开网页本身不会停止Vite；服务连接拒绝属于测试基础设施失败，不能计为通过。
- 已知边界：上传进程硬退出可能留未引用文件，无自动扫描；清理失败仅显式重试。
- A1已在首个真实页面成功后记录打开；A2保存页码/倍率/模式，普通进度保存不改变最近打开时间，下载不记阅读。
- 历史Starlette/httpx弃用与Node颜色变量警告保留，本次不修复。
- 归档：功能/UI已满足用户验收，完整任务闭合尚待5.A1补证；严格校验不能替代专项测试。

## Change 02 P3-A2 已实现与接入点（2026-10-15）

- PDF.js仍锁定6.4.299，原同源Worker/CMap/字体与Nginx .mjs MIME配置保留。PdfPage共享scale/viewport绘制Canvas、TextLayer、搜索临时覆盖层和未来对象层；100ms稳定重绘、完整帧提交、DPR≤2、单页≤16M像素/单边≤8192像素，离屏释放。
- 原continuous/single/spread保留，默认fit-width；所有手动/自动倍率限制0.5–5。加减25个百分点、可小数手输/预设、fit-width/height和仅阅读区域Ctrl+wheel。ResizeObserver监听实际阅读区域；双页使用总宽+间距/最大高度；缩放保留中心或鼠标锚点，显式导航优先。
- PdfThumbnail真实按需Canvas、离屏清零；PdfOutline支持层级/命名及显式目标，无目录和坏目标明确反馈。没有缩略图独立滑块。
- PdfSearch在已有右面板逐页搜索真实可提取文本、NFKC/空白规范化、大小写及Intl.Segmenter全词规则；字符到text item映射支持跨item和旋转高亮。搜索只保留结果/单页文本，旧generation结果丢弃，无OCR/05依赖、无持久标注。
- 0004_reader_progress仅增加原表nullable view_mode/zoom_mode；旧值默认continuous/fit-width，旧PUT {}及旧null字段兼容。新状态写必须progress.version；原Document行锁串行化首次写入，MySQL使用FOR UPDATE当前读校验CAS。pypdf按需验证/缓存物理页数，不改变题录version或原PDF。
- reader/progress先GET恢复，目标页成功后CAS记打开；1秒防抖、持续最多5秒一次，串行保存/离开flush，8秒超时。普通进度写recordOpen=false，不改变lastReadAt。失败保留本地sessionStorage草稿/提示重试并阻止静默离开；409明确选择载入服务端或基于最新版本保存本地。草稿按用户/文献隔离，刷新提示处理，退出/换账号清理。
- reader/context.ts提供真实ReaderContext/SelectionPosition（含逐页textQuote与未旋转CropBox归一化rects）、单调contextRevision、可取消订阅及DOM事件。选区清除/切文献/离开发布真实更新或context-cleared；DPR不进入持久坐标。NoteDraft/Citation仅类型，03–06业务未实现。
- P3-B1接入：复用context.ts选区、PdfPage的reader-object-layer/同一viewport及progress队列的错误处理经验；标注集revision/命令收据/undo必须按B1另建，不能复用progress.version。该A2接入说明为历史；B1现已在0005_annotations完成标注集/命令收据/undo，本轮B2已实现资产，导出仍未实施。

## 下一阶段顺序与协作限制

| 执行顺序 | 任务 | 主要交付物/用户验收点 |
| --- | --- | --- |
| P3-A1 | 1.x 已完成 | 开发/自动化及用户实际验收通过 |
| P3-A2 | 2.x 已验收 | 缩放、缩略图/大纲、搜索、进度/基础上下文；刷新恢复 |
| P3-B1 | 3.1–3.6 已验收、正式交付 | 模型/API/CAS/幂等、六类文本批注、撤销/列表；保存重开一致 |
| P3-B2 | 4.1–4.6 已开发、验证并通过用户验收 | 手绘、三形状、三插入及资产；全部13类验收 |
| P3-C1 | 5.x | 全类型导出矩阵/ADR、快照/权限/清理；Edge/Acrobat可见、原件保真 |
| P3-C2 | 6.x | 多标签完整菜单、公共接入、性能/全流程回归；多文献/窄屏/资源稳定 |

P3-B1/B2验收均已完成；下一阶段为P3-C1（5.1–5.6），尚未启动，等待新会话明确授权。
保留既有未提交及已暂存改动；不reset/覆盖其他成员代码，不自动commit/push或新建分支。
迁移编号串行协调；公共DTO/事件/API变更列出生产者和消费者，避免各成员复制不同契约。
Docker构建/启动由用户手动执行，不改全局设置、不删数据卷、不替用户运行数据库升级。
未经明确要求不archive、不自动开始C1/C2或其他模块；本次文档同步后停止，等待新会话指令。
