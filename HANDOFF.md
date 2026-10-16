# Litera 开发交接

更新时间：2026-10-16。项目根目录：D:\PKU\Projects\Litera。

## 当前停止点

2026-10-16阅读组自由文本补充：单击只打开/定位批注列表，隐藏对象框和控制点、禁止移动/改框；双击先切批注组再原位编辑，短暂区分单/双击以避免打开侧栏重排导致双击落空。顶部拖动条改为35%不透明度，显示/输入共用约3屏幕px左留白，不改几何或保存数据。最终类型/构建通过，生产真实PDF定向3个不同用例分批通过（2+1）、OpenSpec严格6/6；无后端/迁移变化，仍18/36，仅手动重建nginx并Ctrl+F5。详见B1记录末节，等待用户实际验收。

2026-10-16原位编辑补充：注释图标只联动列表，注释新建/编辑在原卡片内完成；自由文本新建及双击原页输入、单击显示八方向控制点，拖动实时预览，字号与框尺寸独立；统一✓保存/×取消、失败保留与补偿取消、切文献/关面板/切工具保护。沿用原box/字号字段及CAS/commandId队列，无API、后端或迁移修改。类型/构建、Vitest50/50、生产真实PDF阅读器全量32/32通过（隔离SQLite），最后工具保护定向验证见B1记录；未跑真实MySQL，仍18/36，仅手动重建nginx并Ctrl+F5，等待实际验收，不进入B2。

2026-10-16右下角通知补充：按用户最新要求，阅读器和文献库所有右下角浮动提示统一3秒自动消失，悬停也不延长；覆盖历史文献库5秒及批注草稿常驻提示行为。隐藏通知不清除草稿，批注列表保留立即保存/导出备份入口，原失败/冲突错误栏继续显示；顶部保存成功仍为1秒。无API/数据库变化，仅需手动重建nginx并Ctrl+F5；仍18/36。测试结果见B1记录末节。

2026-10-16阅读模式对象点击补充：点击注释/自由文本只联动右侧列表高亮，不自动打开编辑窗；仅批注组直接点击编辑，列表编辑按钮保持可用，橡皮擦也限定批注组。类型/构建及真实PDF定向2/2通过，只需手动重建nginx并Ctrl+F5；无API/数据库变化，仍18/36。

2026-10-16注释定位补充：列表导航改为按标注实际SVG显示边界预留PAGE_PADDING=12px，避免气泡尾尖对齐导致主体被顶部裁掉；所有标注统一，保留几何点回退，搜索/大纲不变。类型/构建、真实PDF定位/跨页Rotate定向2/2通过，间距按约12px（3px内偏差）验证。本次只改前端，手动重建nginx并Ctrl+F5，仍18/36。

2026-10-16高亮图标补充：改为黄色背景块+A字形+文字定位竖线，与荧光笔/橡皮擦区分；只改项目内SVG，高亮功能不变。类型/构建通过，仅需手动重建nginx并Ctrl+F5，仍18/36。

2026-10-16上标对齐补充：四类文本标记新增公共显示行排版，上标随正文统一高亮范围，底线/波浪/删除线按正文行基准连续绘制；旧分段标注直接兼容，原选区/JSON/数据库不改写。类型/构建、单测48/48、真实PDF定向3/3通过（上标、精细选择及跨页/Rotate），已检查四类截图。本次仅前端，手动重建nginx并Ctrl+F5即可；仍18/36，等待原论文实际验收。详见B1记录末节。

2026-10-16编辑颜色补充：所有批注编辑窗增加与顶部共用的黄/红/绿/蓝四种常用色，保留自定义与选中态，仅修改草稿、保存时提交。类型/构建及生产真实PDF定向2/2通过（六类颜色与窄屏）。只需手动重建nginx并Ctrl+F5；无后端/迁移变化，仍18/36，等待用户验收。详见B1记录末节。

2026-10-16最新补充：按用户实际截图完成B1八项交互/视觉修复。当前Range精细选择/UTF-16偏移、公共同行几何合并、标记穿透与框退出、字体比例定位及平滑波浪、语义图标、气泡锚点和实时拖拽/取消、顶部居中1秒保存成功通知均已实现；原保存/CAS/收据/补偿撤销沿用。annotations.py仅兼容校验原JSON的可选textRanges与rect.baseline，**无新迁移**。本轮最终类型/构建通过、Vitest46/46、pytest123/123（隔离SQLite）、生产阅读器30个不同用例分批通过、文献库额外冒烟5/5；后续补记见[B1八项修复记录](docs/development/p3-b1.md)。原论文Docker体验及真实MySQL待用户验收。需手动同步重建api/nginx并Ctrl+F5；本轮未运行Compose/业务库迁移/提交。仍18/36，B2/C未启动。

2026-10-16局部UI补充：保留批注列表8px紧凑顶部间距，标题/数量/排序/筛选固定，下方条目独立滚动；选中定位只滚动条目区。ReaderPanel固定内容布局仅作用批注列表，搜索/左导航保持原行为。类型/构建及生产真实PDF定向2/2通过，验证滚动时控件/PDF位置不变、搜索切换及窄屏编辑。仅前端组件/CSS，已部署B1时本次只需手动重建nginx并Ctrl+F5，详见[B1记录末节](docs/development/p3-b1.md)。仍18/36、等待实际验收，不进入B2。

Change 01、02 P3-A1和P3-A2（含UI及缩略图补充）均已通过用户实际功能/UI验收。本轮仅获授权实施02-pdf-reader的P3-B1（tasks 3.1–3.6），六类文本批注、真实持久化/补偿撤销、列表及生命周期已完成开发与自动化验证，18/36。完成后停止等待B1实际验收，不自动进入B2/C1/C2。

最新实现与Windows CMD部署/浏览器验收见[docs/development/p3-b1.md](docs/development/p3-b1.md)。新增0005_annotations接0004，保留原账号/documentId/题录/PDF/progress；三张新表为annotations/document_reader_state/annotation_command_receipts。原件只读；集合revision/对象version与题录、progress独立；新增关联纳入原cleanup_jobs失败/重试事务。B2资产和03–06表未建。

前端复用PdfPage/context真实选区，新PdfAnnotations独立SVG及同viewport，尊重原PDF自带朝向/CropBox，不提供页面旋转功能；页点注释/自由文本可移动、文本框可改框。reader/annotations.ts按文献串行保存，超时查收据、失败保留草稿、已存undo/redo发真实补偿。右侧AnnotationList支持双向定位/排序/筛选，窄屏编辑使用原生顶层dialog。草稿失败阻止路由/活动标签关闭，刷新恢复待确认命令；409不自动覆盖服务端，可导出及显式载入服务端并保留可导出的备份。

本轮类型/生产构建通过、Vitest43/43、后端pytest122/122（临时SQLite）、生产阅读器29项分批通过（11+18）、文献库22项分批通过（5+5+12）、OpenSpec严格6/6；MySQL仅离线DDL，真实MySQL集成未运行。完整证据及失败批次边界见B1记录。历史A1/A2测试及其“待验收/不进入B1”描述仅对应当时阶段，当前以本段及用户最新授权为准。Change 01任务仍33/34，5.A1专项MySQL补证边界不变。

没有运行Docker Compose、业务库迁移、Git commit/push、OpenSpec sync/archive。保留工作区已有修改；需要用户手动重新构建API和前端（已有.env无需初始化）：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
docker compose ps
```

API启动会自动增量迁移到0005；不要删库/卷或重新上传原PDF。完成本轮后只等待用户实际验收。

## 架构与运行

- B/S：Vue 3 + TypeScript + Element Plus；FastAPI + SQLAlchemy/Alembic；MySQL 8.4；Compose三服务。
- Nginx为同源唯一入口，前端固定/api/v1；API/数据库在内网，PDF私有卷仅API挂载。
- 前端依赖锁于frontend/package-lock.json；后端锁于backend/requirements.txt；宿主开发Node 24+、Python 3.12。
- 当前迁移链0001_auth → 0002_documents → 0003_library → 0004_reader_progress → 0005_annotations，API启动自动alembic upgrade head。
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
| 02-pdf-reader / Jensen Zhang | P3-A1/A2用户已验收；P3-B1已实现，等待用户实际验收 |
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
- P3-B1接入：复用context.ts选区、PdfPage的reader-object-layer/同一viewport及progress队列的错误处理经验；标注集revision/命令收据/undo必须按B1另建，不能复用progress.version。该A2接入说明为历史；B1现已在0005_annotations完成标注集/命令收据/undo，资产和导出仍未实现。

## 下一阶段顺序与协作限制

| 执行顺序 | 任务 | 主要交付物/用户验收点 |
| --- | --- | --- |
| P3-A1 | 1.x 已完成 | 开发/自动化及用户实际验收通过 |
| P3-A2 | 2.x 已验收 | 缩放、缩略图/大纲、搜索、进度/基础上下文；刷新恢复 |
| P3-B1 | 3.x 已实现，待验收 | 模型/API/CAS/幂等、六类文本批注、撤销/列表；保存重开一致 |
| P3-B2 | 4.x | 手绘/荧光笔、三形状、三插入及资产；全部14类验收 |
| P3-C1 | 5.x | 全类型导出矩阵/ADR、快照/权限/清理；Edge/Acrobat可见、原件保真 |
| P3-C2 | 6.x | 多标签完整菜单、公共接入、性能/全流程回归；多文献/窄屏/资源稳定 |

每阶段同步测试/契约，交付后等待验收；本次仅完成B1，不自动开始B2或后续阶段。
保留既有未提交及已暂存改动；不reset/覆盖其他成员代码，不自动commit/push或新建分支。
迁移编号串行协调；公共DTO/事件/API变更列出生产者和消费者，避免各成员复制不同契约。
Docker构建/启动由用户手动执行，不改全局设置、不删数据卷、不替用户运行数据库升级。
未经明确要求不archive、不自动开始B2或其他模块；本次完成后停止，下一会话获指令后继续。
