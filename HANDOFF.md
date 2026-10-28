# Litera 开发交接

## 2026-10-28 八类工程规范整理与同步

[规范索引](docs/standards/README.md)下1–8文件均已审订，分别为产品/后端/安全/测试/部署运维/AI应用/数据/评审；根[AGENTS.md](AGENTS.md)与[规范审查技能](.agents/skills/litera-standards-review/SKILL.md)提供常驻入口和流程。未保留重复verification.md。

本次仅同步规范及截图范围中的文档/规则改动，不合并代码：Litera为01/02、0006；Litera-test另有03/04/07及0007/0008。课程HTML/ZIP、.env、数据库/PDF卷、Compose及同学业务实现均未复制。原项目原有运行说明保留。

三份新增来稿已修正AI变量名、手动/实时与连续切换选区的区别、历史译文显式确认、当前校验/重试/费用边界，补实际测试/部署入口及待落实项。两份先前来稿按7/8顺序保留审订结果。本轮只读审查源码/课件、命令入口及文档链接/差异，不宣称已运行完整测试、真实模型、部署或恢复演练；先前三类规范的4项临时SQLite测试仅属Litera-test历史记录，不作为原项目本轮测试证据。

后续按条目/章节记录实际与预期、验证环境、失败/跳过及未测项；用户自行Git提交/推送，本次不执行。

更新时间：2026-10-20。路径基准：项目根目录。

本轮完整功能与最终交互、分批测试证据、暂缓需求、手动部署及GitHub上传步骤见
[2026-10-20交付索引](docs/development/2026-10-20-delivery.md)。
最新快捷面板仅批注模式右键触发（非选中自动弹出），上工具/下颜色两行；上传提示已改为单篇上限MB。
本次只完善文档，未自动暂存、提交、推送或运行Docker；35/36及用户最终验收门槛保持。


## 2026-10-20 账号安全补充

用户明确授权在个人资料页增加修改密码。已接入页面内账号安全表单和POST /auth/password，
校验当前密码/新密码，成功同事务撤销本人全部会话并回登录；无新迁移、不改用户科研数据。
详见[修改密码记录](docs/development/password-change.md)及[API契约](docs/design/api-contracts.md)。
部署由用户手动重建API/nginx；不运行Compose、不提交/推送/同步/归档，不将本增量当成C2实际验收通过。

2026-10-20角度编辑框修正：图片/签名属性框改按未旋转box定位，调角度时固定，移动/缩放时仍跟随。
详见[插入角度记录末节](docs/development/insert-rotation.md)；上轮旋转API已部署时，本次仅需手动更新nginx。

2026-10-20选区右键快捷面板：仅批注模式显示，上排高亮/下划线/波浪线/删除线/注释，下排常用色/自定义色；优先在选中文字上方显示，
悬停保持、离开按距离淡出（50px消失）；复用原批注保存及草稿保护，支持原生全屏。
见[快捷面板记录](docs/development/selection-quick-toolbar.md)。无后端变更，只需手动更新nginx，仍待用户实际验收。

2026-10-20插入对象补充：水印、签名、图片支持同步角度滑块/手动输入（−90°～90°、1°步进），
签名属性移除更换图片；图片/签名旋转接入保存、撤销与导出。无迁移，手动部署需同时更新api/nginx。
详见[插入角度记录](docs/development/insert-rotation.md)，仍等待C2用户实际验收。

2026-10-20阅读器验收反馈：移除“资产管理”入口及面板；图片编辑只保留更换图片，
按用户再次反馈彻底移除重新读取/重试加载入口及相关提示，后台自动回收/撤销租约保持。见[图片入口精简记录](docs/development/reader-asset-ui.md)。

## 当前阶段：P3-C2交付，等待用户实际功能/UI验收

2026-10-17用户已正式授权tasks 6.1–6.6。本轮完善共享标签管理/溢出列表/批量关闭保护、
各篇面板恢复、公共ReaderContext与navigation adapter；保留B1/B2/C1已验收交互和保存机制。
实测1000页/DPR2/500%与10标签轮切，预算稳定，未新增复杂缓存或降低既有采样预算。
500%触发已有像素保护时增加明确提示。无新HTTP端点/迁移，head保持0006_reader_assets。

开发、实际测试批次、资源数据、已知边界和用户验收步骤见 [P3-C2记录](docs/development/p3-c2.md)，
其他成员接入见 [Reader公共接口](docs/design/reader-public-api.md)。
pageNumber现在明确为当前阅读物理页，选区起点由selectionPosition[0].pageNumber取得；
消费者须核对documentId/contextRevision、取消自己的请求/订阅，引用来源未接入返回unavailable。

最终功能与UI体验等待用户亲自验收；6.6用户验收未完成，不提前结束Change 02。
任务当前35/36：6.1–6.5完成，6.6文档已更新但用户验收保持待完成。
本轮有效测试：后端182/182（临时SQLite）、前端65/65、类型/生产构建、文献库22/22、
认证UI10/10及隔离真实认证2/2；阅读器按全量与最终定向分批记录，陈旧布局断言已修正复测通过，
不声称单一批次全量通过。最后C2生产4项、公共导航1项、稳定资源采样1项分别通过。
1000页首帧1.786秒/完整搜索3.953秒，40个Worker创建峰值1，回库Worker与Canvas均0；
回库heap约16.5–16.6MiB、DOM/监听计数稳定，不外推长时耐久或浏览器总RSS。
OpenSpec严格6/6、29份文档154条本地链接及diff检查通过，详细批次和局限见C2记录。
真实MySQL/旧业务升级和Adobe未测试，C1 Chrome/Edge用户确认范围保留，不补造版本或扩大结论。
不运行Docker Compose、不改原件、不删除业务数据/卷；保留本轮之前未提交和暂存的改动，
未自动commit/push/sync/archive，也未开发03–06。仅C2基础前端增量可只更新nginx；本会话密码/旋转代码若未部署，须同时更新api/nginx。
下方C1及A/B记录为历史交接，涉及“C2未授权”的文字不再代表当前授权状态。

## P3-C1历史停止点：已验收，交接完成

用户在本会话明确确认“P3-C1我已验收通过”，并补充“5.5我也已测试，我测试了Google浏览器和Edge浏览器，都能正常显示导出的内容”。
据此P3-A1/A2/B1/B2/C1均已通过实际功能/UI验收，Change 02的1.1–5.6完成，当前30/36。
5.5按本轮用户明确确认的Google Chrome/Microsoft Edge范围完成；Adobe Acrobat Reader未测试，
Chrome/Edge具体版本未提供，不补造为通过记录。真实MySQL专项仍无通过证据，用户验收不等同MySQL集成测试。

下一阶段P3-C2（6.1–6.6）尚未启动，须等待用户另行授权。03–06未开发，不自动进入新阶段，
不自动Git commit/push、同步主规格或OpenSpec archive。当前未提交改动须保留，不reset/clean。
本轮只整理文档与交接，不修改业务代码，不运行Docker、迁移或重新执行历史业务测试，不需再次部署。
文档收尾检查：OpenSpec严格6/6、17份文档108个本地链接目标及git diff --check通过；
证据`.cache/c1-handoff-openspec.json`、`c1-handoff-doc-check.json`、`c1-handoff-status.json`。

## P3-C1最终交付行为

- 全部13类批注导出：高亮、下划线、波浪线、删除线、注释、自由文本、手绘、矩形、圆形、椭圆、视觉签名、水印、图片。没有独立荧光笔。
- pypdf 6.20.1 + ReportLab 4.4.10及OFL Noto Sans SC常规字体，保留CropBox/Rotate/UserUnit与原页数；不增加附录，不修改原始PDF字节。
- 注释为原生Text/Contents/Popup与确定的气泡AP；自由文本/水印使用FreeText语义保存全文，页面内容保持可见和层叠。水印不再使用Stamp，避免Edge额外显示注释图标。不承诺第三方原生可编辑。
- 同步受保护POST /api/v1/documents/{id}/annotated-pdf，expectedAnnotationRevision比对已保存一致快照。临时副本隔离原件/资产，导出期间可继续编辑；下载前复验权限。
- 每API进程并发1、渲染60秒/RSS512MiB、产物200MiB、下载120秒；取消/断线/异常及启动/周期孤儿扫描回收。复用现有CAS/commandId、undo/redo及文献清理；无新增迁移，head仍0006_reader_assets。
- 统一下载下拉菜单提供带批注导出/原始PDF下载及说明，窄屏侧栏复用菜单；原件保留上传名，导出为原文件名_带批注.pdf。草稿须明确处理，不静默丢弃。
- 导出状态为顶部居中轻量浮动通知，成功3秒收起；失败/处理中/草稿选择保留操作。注释悬浮显示/移走消失，单击固定/外部关闭，淡入淡出各100ms。
- 原生全屏入口位于批注列表与下载之间，内收四角还原图标；只将Litera品牌/用户栏以200ms上下滑动收起/展开，文献管理/标签保留，阅读及编辑工具栏常驻正常占位，不覆盖PDF或侧栏。
- 全屏动画结束后统一适应缩放并恢复阅读点；弹层挂到阅读器根容器。Esc由浏览器控制，Litera无Esc退出快捷键，浏览器退出不附带草稿取消/面板关闭。旧顶部感应/工具栏自动隐藏方案已取消。

## 验收与测试证据

各批次独立，不将历史测试冒充本轮重跑：

| 批次 | 实际结果 | 证据 |
| --- | --- | --- |
| C1导出与注释修复 | 后端181/181，临时SQLite；13类×4页结构/独立渲染、原件hash及页数不变 | .cache/c1-stray-backend.log，docs/development/p3-c1-comment-popup.md |
| 原生Edge额外图标 | Edge155.0.4283.45自动打开公开样本，旧版探针复现，修复版与对照像素一致；非人工版本证据 | .cache/c1-acceptance/edge-regression.json |
| 下载菜单/中文命名 | 后端导出33/33、C1浏览器5/5，类型/构建通过 | .cache/c1-menu-*.log |
| 最终全屏布局 | 类型/构建、Vitest62/62、生产Chromium12/12（全屏7+C1五例）；检查200ms双向动画和编辑不遮挡 | .cache/fullscreen-brand-layout-*.log |
| B1/B2定向回归 | 前次生产Chromium15/15含全屏6+C1五例+B1/B2各两例，保存取消/undo/redo/橡皮擦 | .cache/fullscreen-final-browser.log |
| 用户实际验收 | P3-C1整体功能/UI通过；Chrome/Edge导出内容显示正常，用户明确确认5.5 | 本会话2026-10-17确认，docs/development/p3-c1.md |

开发记录：[C1与兼容矩阵](docs/development/p3-c1.md)、[注释/导出交互修复](docs/development/p3-c1-comment-popup.md)、
[全屏最终布局](docs/development/reader-fullscreen.md)、[ADR 0007](docs/design/adr-0007-annotated-pdf-export.md)。
.cache是本机自动化证据目录，不保证随Git传递；正式文档已保留结果摘要和可重复运行的测试/样本脚本。

## 后续接手边界

1. 先读本文件、README及Change 02 proposal/design/specs/tasks，再读上述最终修复记录，以最新实际代码为准。
2. 获授权后仅按C2六项推进多文献完善、公共接入、资源实测、全流程及交接；不借交接修改已验收B1/B2保存和UI。
3. Adobe独立兼容和浏览器版本号属于未提供的专项记录；不得声称已通过。真实MySQL、旧数据升级及大规模资源压力测试仍需独立证据。
4. 不删除用户PDF、数据库或卷，不自动运行Compose/提交/推送/归档；部署继续由用户手动执行，下方历史运行说明保留。

## B2历史交付记录（截至2026-10-16）

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
| 02-pdf-reader / Jensen Zhang | P3-A1/A2/B1/B2/C1用户已验收，30/36；Chrome/Edge显示通过，Adobe未测试；C2未开始 |
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
- P3-B1接入：复用context.ts选区、PdfPage的reader-object-layer/同一viewport及progress队列的错误处理经验；标注集revision/命令收据/undo必须按B1另建，不能复用progress.version。该A2接入说明为历史；B1现已在0005_annotations完成标注集/命令收据/undo，B2已实现资产，C1导出现已实现并获验收。

## 下一阶段顺序与协作限制

| 执行顺序 | 任务 | 主要交付物/用户验收点 |
| --- | --- | --- |
| P3-A1 | 1.x 已完成 | 开发/自动化及用户实际验收通过 |
| P3-A2 | 2.x 已验收 | 缩放、缩略图/大纲、搜索、进度/基础上下文；刷新恢复 |
| P3-B1 | 3.1–3.6 已验收、正式交付 | 模型/API/CAS/幂等、六类文本批注、撤销/列表；保存重开一致 |
| P3-B2 | 4.1–4.6 已开发、验证并通过用户验收 | 手绘、三形状、三插入及资产；全部13类验收 |
| P3-C1 | 5.1–5.6 已验收 | 13类导出、Chrome/Edge用户显示验收、原件保真；Adobe未测试 |
| P3-C2 | 本轮已授权开发与验证，等待用户实际功能/UI验收 | 多标签完整菜单、公共接入、性能/全流程记录见P3-C2文档 |

P3-B1/B2/C1验收均已完成；C2本轮已获授权，最终用户验收尚未完成，不自动结束Change 02。
保留既有未提交及已暂存改动；不reset/覆盖其他成员代码，不自动commit/push或新建分支。
迁移编号串行协调；公共DTO/事件/API变更列出生产者和消费者，避免各成员复制不同契约。
Docker构建/启动由用户手动执行，不改全局设置、不删数据卷、不替用户运行数据库升级。
未经明确要求不archive；C1验收文档交接后停止，不自动进入C2或其他模块。
