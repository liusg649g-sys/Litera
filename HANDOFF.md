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

## 2026-10-21：独立 Windows 人工测试入口

新增 scripts/local-site.ps1 与 scripts/local_site.py，复用现有 backend/.venv、前端node_modules和SQLite/Alembic启动方式，无需Docker。项目根目录执行 .\scripts\local-site.ps1 start（stop/status同入口），浏览器使用 http://127.0.0.1:5177。持久测试数据位于被忽略的.cache/local-site，不能当普通缓存清理。详细隔离边界、日志、磁盘阈值见LOCAL_DEVELOPMENT.md。

本轮实际本地Chromium定向7/7通过：认证/改密、上传阅读、批注与带批注PDF导出、插入对象角度、全屏、多文献菜单及应用内导航；停止重启后数据数量保持。没有运行MySQL回归或Docker部署，用户人工验收待进行。此前documents.py时间戳候选修改保留，SQLite结果不证明MySQL问题已修复。

## 2026-10-22 P0：上传时间戳一致性（MySQL验收待补）

保留documents.py save_upload已有commit后refresh(doc)候选修复：文献created_at/updated_at迁移是普通DateTime，MySQL默认fsp=0；应用生成UTC微秒且SessionLocal expire_on_commit=False，未刷新时上传DTO保留内存精度，GET读取落库值。无迁移、无API字段变化，不截断时间或放宽断言。当前真MySQL不可用，未启动Docker，因此仍不能称MySQL修复验收通过。

新增test_documents.py两组数据库存储规范化回读用例（同秒及跨秒，明确是注入SQL变化的SQLite测试而非MySQL），以及refresh失败仍保留已提交文献/PDF的回归。临时SQLite：定向4通过；完整documents44通过；library/reader_progress28通过，共72个不同用例通过，定向4与44重叠。测试进程内移除refresh的反例2失败（预期）；业务源码未被反例修改。日志.cache/p0/，本轮未重启5177/API或访问其业务数据，未提交/推送。下一步需独立、明确授权的MySQL litera_test环境复跑原始失败用例与回归，禁止指向业务库。

## 2026-10-22 P2：PDF选区翻译接入（真实模型待配置验收）

已接ReaderContext/文字层及独立翻译面板，手动默认、实时500ms稳定/拖动抑制/去重取消与迟到失效、收起保留与暂停、方向/来源/复制/重试。新后端POST /documents/{id}/translations复用会话/Origin/CSRF及owner权限，校验原PDF页码；不建表、不改迁移、不开发笔记。model_service提供可替换协议适配层，当前支持OpenAI兼容接口。backend/.env仅供翻译配置读取，APP_ENV=test忽略私有文件；API Key不进入前端/日志。

候选网关ai-gateway.devops.hello1023.com/v1和course-chat由用户提供，但模型名/协议/真实译文未验证；实际backend/.env尚不存在。不要把Mock成功结果称为真实AI验证通过。运行5177已加载接口，未配置时明确503，不返回假译文。操作与配置见docs/development/p2-translation.md；原03任务规划新增进度说明但不宣布全部完成，不接04笔记或自动归档。

本轮最终API相关临时SQLite/Mock测试87通过；前端76通过，类型及构建通过；隔离PDF浏览器8通过（模型成功及剪贴板为Mock，未配置错误走真实测试后端），含C1导出/全屏/C2标签回归。最初浏览器1失败/6通过暴露工具栏文字溢出点击相邻按钮，修复并复测通过；随后补实时取消恢复单测。Windows本地按原入口stop、完整备份验证、start，业务7账号/9文献/8批注/1资产及文件哈希保持。P0候选和原测试改动均保留；真实MySQL仍未验收，未Docker、提交或推送。用户人工验收待进行。

## 统一AI服务层增量（2026-10-22）

新增ai_service.py：ModelProfile、ProfileResolver、ModelService.complete和统一Adapter.complete；翻译提示词留在model_service.py，翻译API通过请求依赖model_resolver解析配置。推荐backend/.env中AI_*字段，兼容TRANSLATION_*，Key不进入前端或repr。AI_MODEL_VERIFIED默认false，未配置/未确认拒绝真实请求。

当前本地开发者配置与未来用户配置分离；用户scope携带owner_user_id并与认证用户校验，没有用户密钥表/管理UI或全局用户密钥缓存。用户模块以后替换请求级resolver，缺失自有配置不能静默共享别人的Key。详见docs/design/model-service.md。

本轮隔离SQLite/Mock回归33通过，隔离浏览器未配置错误1通过；无真实模型调用。未重启5177，当前健康200仅证明原服务在线，新统一层尚未加载到正式本地进程。未写业务数据、改迁移、Docker或Git提交/推送。保留P0及全部既有改动。

## P2-A手动翻译验收准备完成（2026-10-22 14:50）

已有翻译API/手动面板复用，本轮只补响应来源（文献/物理页/方向/contextRevision/原文）严格校验、旧页结果提示，以及PdfReadError安全错误。新增第二页单词/句子/段落精确选区、加载/手动不自动请求测试，不重写已有功能；既有实时代码保留，P2-B不在本轮验收范围。

本轮临时SQLite/Mock后端97通过，前端78通过，手动/既有阅读器浏览器8通过，类型/生产构建通过。模型配置与验证均为空/false，无真实模型请求，不能宣称真实翻译质量已通过。安全预检/完整备份验证后一次stop/start，统一模型新层和P2-A已在5177加载，首页及健康200；业务数量及PDF/图片/会话密钥哈希保持。详见统一交接第29节；等待用户人工验收。

## 2026-10-22 tcsec_pdf第5页文字映射异常

已只读复现：主字体无ToUnicode且使用Gxx不透明字形名，PDF.js原始5045字符中3381为异常控制字符；浏览器原生Range文本与Litera选区23字符逐字一致，侧栏未额外引入乱码。未读取系统剪贴板或猜测原文。新增前端按字体/字符可靠性警告与翻译阻断，后端独立拒绝异常字符和来源页不透明映射；不改原PDF、原始选区或批注几何。ReaderContext仅新增可选textExtractionIssue，公共契约文档已说明。

后端临时SQLite/Mock115通过，最终前端87通过/构建通过，浏览器7通过（含显式本机提供的真实第5页、正常选区及既有批注导出/标签/全屏）。真实PDF不进入仓库；无法可靠提取不发送模型。按原入口备份后一次安全重启，5177/8002健康200，7账号/9文献/8批注/1资产及文件哈希保持。映射无法无依据还原；建议权威文字映射版本或独立OCR副本并人工校对，当前不做OCR。规则保守，可能拒绝同字体/同页可打印片段。详见docs/design/pdf-text-reliability.md及统一交接第30节。


## 2026-10-23 P2：有界真实探测、排版断词及来源显示

复用统一AI服务层和AI_*配置，新增输出Token上限（AI_MAX_OUTPUT_TOKENS默认2048）与显式scripts/verify_model.py --probe，最多两句公开合成文本/每句128输出Token，失败停止，不自动修改验证标记。未配置密钥时仍提示“模型未配置”；本轮实际backend/.env已由本地使用者创建，但检测AI_API_KEY为空，故真实请求0次、英中双向译文未验证。不能将下列Mock通过描述成真实翻译通过。

新增pdf_text.model_input_text：原始选区与定位不变，先执行异常映射保护，再在实际PDF唯一字符位置、同列相邻行及限定词形证据下合并disor-/ders、thera-/pies、ul-/trasound；未知/重复/复杂布局/真复合词原样。模型输入独立，响应仅变化时新增可选modelInputText/normalizationCount。面板来源改“文献标题 · PDF第X页”，空标题回退；重复映射警告仅一次，规范化输入可展开核对。无迁移、依赖或笔记/P2-B实现变化。

本轮最终后端142通过（临时SQLite/真实合成PDF/Mock模型），前端93通过，类型与构建通过；隔离浏览器11通过/1跳过（未提供私人PDF opt-in）。覆盖既有批注PDF导出、多文献标签及全屏。按既有安全流程预检、停服、完整联合备份20文件7432387字节并校验后一次启动，5177/8002健康200；7账号/10文献/8批注/1资产与重启前相同，资产与会话密钥哈希保持。真实MySQL仍未验收，未Docker/提交/推送。详细命令、备份路径及证据见统一LITERA_HANDOFF第31节。


## 2026-10-23：course-chat真实双向验证与本地加载

用户在私有backend/.env填Key后，本轮通过现有统一OpenAI兼容适配器向用户指定网关调用course-chat别名，固定两句普通合成文本，各最多128输出Token、无重试。两次实际HTTP200，约8.59秒：英文光学显微研究句译为“光学显微技术被广泛应用于科学研究中。”；中文句译为“Optical microscopes are widely used in scientific research.”。译文合理，证明该网关当前接受此别名及已适配对话请求形状，不保证所有模型协议或服务未来可用。

仅在上述真实成功后启用私有配置验证状态，其他配置字节保持，Key不复制、展示或提交。.env由.gitignore忽略且未跟踪。按已审核入口完成预检、stop、完整备份校验、start及数据复核，5177/8002健康200；7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。未改业务代码/结构/数据、未Docker或Git提交推送。正式网站登录后的真实选区翻译待用户人工验收；本轮不再额外调用私人PDF，详细备份和证据见统一LITERA_HANDOFF第32节。


## 2026-10-23：翻译繁忙、性能观测及来源/工具栏优化

本轮实际隔离复现旧前端cancel不等于后台结束：2次浏览器取消后，2秒Mock模型仍占槽，第三次32ms返回429 TRANSLATION_BUSY。后端新增断连取消并await清理，保留总并发2/每用户20次每分钟/原超时、不增加重试或无界队列；繁忙拒绝不再消耗调用计数。相同Mock复测取消路由约160/154ms结束，第三次正常200。历史2次429缺少错误码，不能认定均来自网关或本地。

前端真实single-flight+最多1条最新候选，500ms稳定后登记、同源重复点击复用在途Promise；429暂停自动翻译仅手动重试恢复；旧结果来源校验、乱码保护不变。补会话epoch：旧账号迟到429不影响新会话，新账号不继承实时自动外发。UI显示“当前选区译文/上一条译文”，上一条可查对应原文；toolbar“面板”开关（实时展开可能调度）与“翻译”快捷请求，同面板按钮且忙态禁用，2按钮单独自适应宽避免溢出。

新增无敏感信息的Server-Timing/网关状态响应头及translation_metrics日志。本轮2次受控真实course-chat公开短句采样：修改前浏览器2.279s/后端2.195s/网关2.166s，修改后3.176s/2.611s/2.584s，两次API/网关均200。浏览器口径含自动化点击等待，后段采样与本机检查负载存在重叠；单样本不能证明单次加速，网关span不能拆分网络/排队/推理。未观察到本轮真实网关429，Mock限流测试不能称服务商实际限流。详见docs/development/p2-translation-performance.md。

实际自动化：后端150通过（临时SQLite/合成PDF/Mock），最后PDF失败计时增量定向37通过；最终前端107通过、类型构建通过；浏览器14通过/1跳过，最后会话边界增量后定向5通过（重叠批次不相加）。按原安全流程预检/停服/联合备份验证/一次start，5177与8002健康200，7账号/10文献/8批注/1资产及PDF/图片/会话密钥哈希保持。无.env/Key/模型配置、数据库结构或P0修改，无Docker/提交/推送。实际备份与完整证据见统一交接第33节；等待用户人工验收，不进入笔记或其他开发。


## 2026-10-23 P3-A：笔记基础管理（隔离完成，真实库迁移待确认）

用户已声明P2翻译人工验收通过，本轮沿用并更新Change04规约，strict校验通过；不进入P3-B/P3-C。新增独立notes及note_documents多对多，UUID幂等创建、owner/Origin/CSRF校验、version CAS、独立关联与解绑/全局删除确认。前端纯文本编辑，800ms串行自动保存、保存失败/冲突提示与按账号会话草稿、旧响应失效，独立笔记栏与翻译栏共存，无新增依赖。

新增0007只建两表/索引（MySQL InnoDB/MEDIUMTEXT/DATETIME(6)/JSON），不改旧表或PDF；SQLite隔离升级/重复升级/禁止破坏性降级与旧数据资产保留已测。真实MySQL未测，P0真实MySQL验收仍未完成。

本轮最终：后端完整临时SQLite+Mock回归306通过/0失败/0跳过；前端127通过/19文件，vue-tsc+build通过（大chunk告警）；笔记真实HTTP+临时SQLite浏览器7通过；既有翻译/C1/C2/全屏浏览器28通过/1私人PDF opt-in跳过。翻译及故障注入为Mock，本轮未调用真实模型。

5177/8002仍在线，实际库保持0006，7账号/10文献/8批注/1资产数量和11资产SHA256不变；没有迁移/重启该环境。前端遇旧API明确“笔记尚未部署”。P3-A候选在独立持久预览http://127.0.0.2:5180（API8003，.cache/notes-preview，0007独立SQLite）可验收，新注册专用账号/上传非敏感测试PDF；该预览不加载真实AI配置，不与5177共用Cookie/数据。启动/状态/停止用scripts/notes-preview.ps1，停止保留预览数据。

源码/迁移/联合备份/失败处置及人工步骤见docs/development/p3-a.md；完整本地证据见统一LITERA_HANDOFF第34节。真实5177停机联合备份验证与迁移须用户另行确认，不要直接运行会upgrade head的local-site.ps1 start。未Docker、提交或推送；原P0/P2及其他修改保留。用户P3-A人工验收尚未进行。


## 2026-10-23 P3-A-Fix：笔记解除/删除缓存及反馈

用户第一轮多笔记/自动保存/独立侧栏/跨文献关联/刷新重登通过，解除关联/删除显示异常。本轮先复现4项失败：个人缓存关系未同步、已删笔记残留、旧GET复活条目、快速文献切换旧状态晚生效；真实临时SQLite/DB验证后端解绑和全局删除正确，不把截图原因唯一归结为某路径。

仅修notes.ts/NotesPanel.vue：使用解除响应DTO同步关联，立即清当前/个人列表，读请求/文献切换序号及目标保护，明确成功和后续读取失败，重试只GET，保持全局删除二次确认。后端业务/模型/迁移和P0/P2候选不改；测试补notes单测/E2E/后端精确关联验证。

本轮后端26通过，前端137通过/构建通过，笔记浏览器9通过（最后2项重叠复测通过），翻译聚焦浏览器10通过/1私人PDF跳过；Mock模型/读故障与真实临时SQLite分开，无真实模型/MySQL调用。5180通过Vite提供修复模块，未重启后端；现有账号/笔记不作写入测试。原5177库仍0006及7/10/8/1数量/资产哈希保持，预览仍0007及1账号/2文献/3笔记/4关系保持。详见docs/development/p3-a.md和统一报告第35节，等待预览人工复验；不进入P3-B或真实库迁移，无Docker、提交、推送。


## 2026-10-23 P3-A：完整关联文献展示与PDF导航

按用户明确方案新增纯展示NoteDocuments.vue，展示DTO.documents全部可访问有效文献，含当前，无当前ID过滤；数量/逐行完整长标题及hover/current徽标，编辑器与个人候选共用。NotesPanel.openDocument复用navigateReader保护性GET/原路由草稿守卫/真实PDF加载，当前关联文献切标签携带同N、不改变关系。个人候选点击关联文献标题只打开PDF，不隐式关联笔记到来源文献。

仅前端及文档/测试变更，所有后端源码/测试/迁移SHA256与开始相同。最终20文件149单元组件通过，类型/构建通过，笔记浏览器11通过（另2项截图改进重叠复测通过）。浏览器实际验证PDF、长标题/标识、同N NoteDTO/版本完全相等且导航期间notes写请求0；失败导航/解除保留、成功解除才更新、确认删除才移除，Mock仅故障和翻译。新截图已根代理查看。

5180 Vite已提供新组件且健康200，现有API未重启；原5177仍0006及7账号/10文献/8批注/1资产，预览0007及1账号/2文献/3笔记/5关系均与本轮开始相同，已有PDF/图片哈希保持。注意本轮开始预览关系已为5，不把前次第35节的4误当本轮基线。未现有业务写入/数据库结构变化/Docker/密钥/提交推送。用户保存后刷新5180人工验收，4.3仍待确认，不进入P3-B。详见统一交接第36节。


## 2026-10-23 P3-B：原文/译文保存到结构化笔记来源

复用0007 `notes.sources` JSON，无新迁移：正文保持可编辑纯文本，PDF原文与翻译结果保存为独立只读来源块，快照文献ID/标题/文件哈希/PDF页码/选区元数据。`POST /api/v1/notes/captures`支持新建或CAS追加、显式link/keep关联、operationId幂等和大小限制；服务端重新读取PDF核验页文字并拒绝异常映射。翻译来源必须携带绑定用户/文件/页码/原译文/方向/contextRevision的短期签名，历史结果需明确确认；Mock明确标记，不能冒充真实模型。

前端增加PDF“添加到笔记”、翻译“保存到笔记”、新建/当前/个人笔记目标选择及结构化来源卡。切文献、解除关联或编辑正文不会篡改已保存来源。关键实现和边界见[开发记录](docs/development/p3-b.md)、[API契约](docs/design/api-contracts.md)、[数据模型](docs/design/data-model.md)和[ReaderContext](docs/design/reader-public-api.md)。

最终后端隔离SQLite/Mock组合122通过；迁移3通过（含MySQL离线DDL，不是真MySQL）；阅读/批注/导出回归118通过。前端176通过、类型和构建通过；P3-A浏览器11通过；P3-B真实HTTP/临时SQLite/PDF.js/合成PDF浏览器9通过。P2浏览器整组首次27通过/1私人PDF跳过/1个测试时序失败，测试夹具加闸门后该用例定向1通过，未重跑整组。

5180预览在完整备份并校验后已加载P3-B，前端/代理/API健康均200，新路由匿名401；预览使用显式隔离Mock，不读真实模型配置。重载前后1账号/2文献/3笔记/5关联与PDF哈希不变。备份：`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3b-20261023-191156`，9文件/12660913字节/逐文件SHA256一致/SQLite完整性ok。

5177/8002在本轮加载前已被既有磁盘保护自动停止，本轮未启动；0006及7账号/10文献/8批注/1资产与行/文件哈希保持。真实MySQL并发行为、真实模型P3-B联动和用户人工验收尚未完成；不迁移5177，不自动进入P3-C。

## 2026-10-23 P3-B-Fix：正常 PDF 摘录误拒

用户在5180保存正常CFF字体PDF第1页原文时稳定触发`PDF_TEXT_NOT_FOUND`。诊断确认ReaderContext页码/原文/position契约正确，当前原文与历史Mock译文使用各自来源；根因是后端只用pypdf整段规范化字符串核对，而PDF.js/pypdf在跨行、标点、字体分段及选区首尾半词上不同。未关闭校验，也未改写保存原文。

新增`pdf_source_validation.py`和`pypdfium2==5.14.0`双提取器校验：保留异常字体/字符保护，仅接受同页精确文本或连续有序Unicode词序；跨行断词需真实换行，首尾最多允许半词，中间词全等，缺词/乱序/普通复合词误拼仍拒绝。`note_captures.validate_pdf_source`显式关闭PDFium资源，并因最终并发测试实际触发Windows原生访问冲突，增加进程内锁只串行化PDFium原生区段。真实PDF opt-in浏览器回归同时通过正常原文保存和历史`isolated_mock`译文自身来源保存。

最终自动化：并发摘录3项连续3轮均通过，后端相关124 passed；前端176 passed、类型/构建通过；P3-B浏览器10 passed，锁修复后真实PDF定向再跑1 passed（真实HTTP/临时SQLite/PDF.js，翻译为隔离Mock）。5180继续明确Mock；加载备份为`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3b-fix-20261023-201043`，17文件/12688453字节/逐文件SHA256一致/SQLite完整性ok。测试构建时D盘短暂低于保护阈值使5180按设计停服；最终测试后只重启5180并复核健康/数据。5177、Docker、真实模型/MySQL未操作；等待用户复验，不进入P3-C。完整失败过程、命令和Git状态见统一LITERA_HANDOFF最新章节。

2026-10-24最终复核：PDFium并发原生崩溃已由仅覆盖其原生区段的进程锁修复；并发3项三轮、后端124项和报告PDF浏览器1项均通过。测试临时占用曾使D盘低于阈值并让预览按设计停服，未下调保护；C/D稳定采样后受管启动成功，12秒后5180/代理/8003均200，数据库完整性/外键/全部表脱敏哈希与备份一致。当前人工入口可用。

## 2026-10-24：5180再次因D盘保护停服，数据完整

用户报告ERR_CONNECTION_REFUSED后只读检查确认5180/8003无监听、manifest/残留PID/端口冲突均无；最新supervisor唯一退出原因是D盘低于10GB。当前D盘仅约10.076GB，40秒20次采样仅高于阈值约75.7MB，因此按用户要求未强行启动或修改保护阈值。当前与`notes-preview-p3b-fix-20261023-201043`备份的SQLite完整性/外键/逐表脱敏哈希及2个PDF哈希完全一致：1账号、2文献、4笔记、6关联；结构化来源块为0，与备份一致，无半写入。需用户先额外释放D盘空间（建议至少5GB、达到约15GB可用）后再只启动5180一次并验收；5177/Docker/业务代码/数据库均未操作。完整证据见统一报告第39节。
## 2026-10-25 P3-C1：本人笔记关键词搜索（5180待人工验收）

用户确认P3-B三组人工验收全部通过后，仅授权P3-C1。Change04新增第7节并strict有效；不新增迁移/依赖。新增认证只读`GET /api/v1/notes/search?q=&page=&pageSize=`，只搜索本人已保存笔记标题、正文、结构化PDF原文和译文，Unicode字面量部分匹配、英文大小写不敏感，特殊字符无SQL/通配符语义；按笔记唯一、分页、有限安全摘要，不因多文献关系重复。

前端笔记面板新增350ms防抖搜索、旧响应失效、加载/空/错误重试、字段/页码与纯文本高亮、点击结果复用草稿保存守卫、清空恢复当前文献列表。搜索本身不写笔记、不搜索未保存草稿或整篇PDF；PDF精确定位留P3-C2。

自动化：后端完整354通过；前端完整180通过/25文件；类型与生产构建通过（既有大chunk告警）；笔记真实HTTP/临时SQLite浏览器12通过；P3-B来源浏览器9通过/1本机私有PDF opt-in跳过，实际覆盖原文和隔离Mock译文搜索。无真实MySQL/模型调用。

5180正常停服后一致备份到`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3c1-20261025-204359`，37文件/12,728,602字节/逐文件SHA256一致/SQLite完整性与外键通过。单次重启后5180/代理/8003均200，OpenAPI含搜索路由；1账号/2文献/4笔记/7关联/1来源块及2个PDF哈希保持，90秒D盘稳定，原10GB保护未改。5177/Docker/CampusClaw/真实Key未操作，未提交推送。等待用户人工验收7.6，不进入P3-C2。

## 2026-10-25 P3-C2-A：笔记来源 PDF 准确跳页（5180待人工验收）

用户明确P3-C1五项人工验收全部通过后，仅授权P3-C2-A。Change04补充可靠来源页导航规约，8.1–8.5完成，8.6用户验收保持未完成；不进入P3-C2-B页内高亮。无新迁移、表、依赖、AI/OCR或5177改动。

受保护DocumentDTO的attachment增加已有PDF `sha256`。`navigateReader`在来源导航时先GET目标文献并核对本人权限、保存哈希及已知pageCount，再复用ReaderPage标签/路由守卫/真实PDF加载/numPages和跳页。来源卡增加“查看原文”；NotesPanel先flush既有800ms自动保存队列，保存失败/冲突阻止跳转，快速点击使旧请求失效；跨文献成功后恢复同一笔记，不新增/解除关系。哈希缺失/变化、删除/越权、非法页码或加载失败均提示“无法可靠定位来源”，不按标题或正文猜测。本阶段不使用选区坐标做高亮。

自动化实际结果：后端完整临时SQLite/Mock `354 passed`；前端Vitest `25 files / 184 passed`；生产构建通过（仅既有大chunk告警）；P3-B/P3-C2-A Playwright `11 passed / 1 skipped`（跳过既有本机PDF opt-in）；P3-A/P3-C1 Playwright `12 passed`；OpenSpec strict有效。真实MySQL未测，5180现有账号的人工作业仍待用户执行。

5180重载前正常停服，完整备份到`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3c2a-20261025-212455`：41文件/12,749,567字节，逐文件SHA256差异0，备份SQLite完整性ok/外键0。单次受管启动后首页、代理健康、8003健康均200，前端实际模块含“查看原文”和`SOURCE_VERSION_MISMATCH`；API/监督器新日志无错误。30秒D盘最低/最终约16.963GB，10GB保护未改。

启动前后笔记业务集合保持1账号/2文献/5笔记/8关系/2来源块、2个PDF且哈希一致。因已有5180浏览器标签自动重连，日志记录一次GET文献/进度/PDF和一次PUT progress；逻辑库仅一篇文献`last_read_at`及其`reading_progress.last_read_at/version`正常更新，不得描述为数据库逐字节不变。笔记正文、来源、关联和PDF未变化。

分支`local/litera-dev-20261020`，HEAD `947dc3cc6381ce4b19d587762950f381b6e31100`；既有P0/P2/P3未提交和未跟踪文件全部保留，无暂存、提交、推送、重置、Docker、CampusClaw或真实Key访问。关键文件和测试见`docs/development/p3-c2-a-source-navigation.md`及统一交接报告第45节。人工入口`http://127.0.0.2:5180/`；验收通过前不进入P3-C2-B。

## 2026-10-26 P3-C2-B1：可复核 PDF 选区的临时高亮（5180 待人工验收）

用户已明确 P3-C2-A 五项人工验收通过，本轮只完成 B1。现有来源首个物理页同时具有合法矩形、`textQuote` 和 PDF.js `textRanges` 时，点击“查看原文”会在 C2-A 的权限、PDF SHA256、页码、标签及草稿保护通过后，等待当前 TextLayer，按保存的文字项及 UTF-16 范围逐字复核，使用 DOM Range 绘制多个非交互临时高亮并只滚动一次。缺少范围、越界、文字层变化、无可见矩形或超时只跳到可靠页面，不做模糊匹配。新来源、文献切换、账号变化或阅读器销毁会清理旧高亮；缩放/虚拟化重绘可重建，但不会再次抢夺滚动。

没有后端、迁移、数据库、PDF、批注或依赖改动。新增 `frontend/src/reader/sourceHighlight.ts`、`frontend/tests/source-highlight.test.ts`、`docs/development/p3-c2-b1-source-highlight.md`；修改 `PdfPage.vue`、`ReaderPage.vue`、`NotesPanel.vue`、公共 `navigation.ts`、相关单测/真实 PDF.js 浏览器测试、Reader 公共契约及 Change04。OpenSpec 9.1–9.5完成，9.6保留给用户验收；B2/B3未开始。

实际验证：前端 Vitest 26文件/190通过；`vue-tsc --noEmit && vite build`通过（1707模块、既有大chunk提示）；后端笔记/来源临时SQLite 73通过，1条既有弃用警告；P3-B/C摘录 Playwright 13通过/1个本机私有PDF opt-in跳过；Reader公共导航及文字批注 Playwright 2通过；OpenSpec strict通过。多行测试中先发现测试对浏览器Range换行的预期错误，随后实际暴露“检查所有文字层span而非只检查来源引用span”的过严降级，均修正后完整回归通过。

5180未停止或重建，Vite实际返回新 `sourceHighlight.ts` 与临时层代码；5180首页、代理健康及8003健康均HTTP200。当前预览库和已验证C2-A备份均SQLite完整性ok、外键0，均为1账号/2文献/2文件/5笔记/8关联/2来源块；2个PDF合计12,338,756字节、相对路径/大小/SHA256差异0。最终C/D可用约14.92/16.74GiB，高于既有十进制10GB保护阈值。分支 `local/litera-dev-20261020`，HEAD `947dc3cc6381ce4b19d587762950f381b6e31100`，暂存0；既有全部未提交/未跟踪修改保留，未提交、推送、重置，未操作5177、Docker、CampusClaw、真实Key或MySQL。人工入口 `http://127.0.0.2:5180/`，用户验收前停止在B1。

## 2026-10-26：翻译/笔记收尾只读审查

用户确认P2、P3-A/B/C1/C2-A/B1均已人工验收，暂停旋转与跨页连续高亮增强。本轮仅静态核对原始选题、Git基线及本地实现、历史测试和只读健康/SQLite完整性；没有修改业务代码、配置、规约或数据，没有启动/重启服务、Docker或真实模型调用。

原始课程明确待补业务是AI回答保存到笔记（当前kind只有PDF/翻译，NoteDraft/AnswerDTO类型不等于接入实现）；需与05/06协调服务端来源校验/引用版本/保存契约。真实模型→笔记完整联调、真实MySQL及安全/生命周期专项仍待补证，不把已有核心误报未实现。旧Change03任务、README和公共DTO需后续对齐当前M:N/签名回执设计；本轮未机械勾选任务。

完整A/B/C/D表、接口协调、个人模型安全扩展方案和分阶段验收建议见上级LITERA_TRANSLATION_NOTES_REVIEW_20261026.md；统一交接第47节。当前5180/代理/8003均200，预览SQLite完整性ok/外键0，1账号/2文献/6笔记/10关联/4来源块。分支local/litera-dev-20261020，HEAD947dc3cc6381ce4b19d587762950f381b6e31100；0暂存/28未暂存/72未跟踪全部保留，无提交推送或5177迁移。等待用户审查，不开始下一阶段。

## 2026-10-26：AI回答保存笔记接口契约（设计稿，未实现）

新增docs/design/ai-answer-note-contract-v1.md，完整核对Change04/06、P3-B来源块/事务/前端三目标与草稿机制。本地QA仍仅规约/目标类型，没有QA路由、回答模型/表/面板；共享模型适配器不等于问答实现，其他成员未提交进展待确认。

推荐06提供服务端owner绑定的不可变answerId+revision读取/resolver；04复用/notes/captures新增ai_answer分支，后端取权威问题/回答/引用快照，不信任客户端来源字段。合法none回答经明确确认可作为未核实AI内容保存，无页码或原文按钮；错误引用/权限/失效/服务故障不能降级绕过。沿用多对多、CAS、幂等和草稿保护，增加同note同回答版本去重；AI引用只复用可靠页跳转，不伪造B1坐标。

笔记JSON预计无需表迁移，06/05稳定回答与证据持久化可能需要新迁移，需协调head/编号。契约明确S0审核、S1临时SQLite/FakeResolver、S2真实来源对接、S3安全预览/人工验收及完整回归矩阵，均未执行；等待用户审核，不自动开发。

本轮只有契约与交接文档变化，未改业务/规约勾选/数据库/配置，未访问5177或5180、Docker、CampusClaw、真实Key或实时GitHub。分支local/litera-dev-20261020，HEAD947dc3cc6381ce4b19d587762950f381b6e31100，0暂存/28未暂存/73未跟踪；全部既有工作保留。统一LITERA_HANDOFF第48节记录完整证据。


## 2026-10-26：P3-D1 笔记侧AI回答适配（隔离Mock，非真实QA联调）

复用P3-B captures/目标选择/幂等/CAS/草稿机制，新增可替换服务端AnswerResolver（默认不可用）、受保护笔记侧回答预览及ai_answer独立JSON块。浏览器仅传ID/修订/确认；服务端读取权威问题/回答并核对归属、PDF实际摘要、证据绑定、页码/原文。无引用须明确确认“未核实”，校验失败/越权/过期/故障不可降级。相同笔记+回答修订去重，不恢复已解除关联；无表结构/迁移/依赖变化。

AI答案、问题与可信引用分开展示并纳入搜索，引用复用页级导航、不伪造PDF.js高亮。固定Mock与合成PDF仅隔离脚本显式启用，正式应用无测试路由，启动不播种数据。内部字段仍待06负责人确认，未开发真实QA/RAG/问答存储/问答面板。

最终后端临时SQLite140通过；前端199通过、类型/构建通过；临时5182/8005真实PDF.js浏览器16通过/1私人PDF可选案例跳过。模型均为Mock，不代表真实QA、真实MySQL或用户验收。已验证完整备份后一次安全恢复5180，原有业务记录/来源/PDF指纹保持，10GB保护不变；未访问或修改5177/Docker/CampusClaw/真实Key，未提交或推送。

实现、测试失败修正与验收步骤见docs/development/p3-d1-ai-answer-notes.md、契约v1实现映射与统一交接第49节。D1等待用户人工验收；不自动进入D2。


## 2026-10-26：P3-E1专项测试与D1最终人工验收

用户明确D1六项全部通过。E1仅测试/缺陷核查，未开发新业务或接真实模型/QA。既有后端251、前端199先通过；新增11个后端组合和1个真实PDF.js生命周期用例，最终后端262通过、前端199通过/类型通过、浏览器去重40通过/2私人PDF可选跳过。覆盖双账号同PDF字节、无效会话、多来源删除恢复/重传、词句段落、剪贴板/超时/限流/竞态/CAS/草稿与P2/P3核心回归，均为临时SQLite/明确Mock。

只修正两项测试设施：e2e_server临时cwd/TMP与环境配置隔离；FixedMockAnswers漏软删除过滤导致404误报503。无backend/app、frontend/src、数据库结构或迁移变更，不放宽校验。5180保持运行，当前数据/文件指纹不变；因未重启，运行中的Mock尚未加载软删404修正。真实MySQL、真实模型质量/限流、真实QA均未验，不把离线DDL或Mock当真实集成。

详细矩阵、历史失败及修正、测试文件、环境完整性与E2建议见docs/development/p3-e1-special-tests.md和统一交接第51节。等待用户审核E1，不推进E2/D2，不提交或推送。


## 用户自定义模型设置 v1（2026-10-26，本地增量，未提交）

Change07已实现个人设置/settings/ai、用户模型CRUD/显式连接测试、DPAPI CurrentUser密文与用户模型翻译，复用统一AI服务及P2/P3来源回执。详见[开发验证](docs/development/user-model-settings.md)和[安全/API设计](docs/design/user-model-settings.md)。backend/.env.example增加默认关闭USER_MODELS_ENABLED；不包含真实Key。

新增0008_user_model_profiles，仅在临时测试及新的独立实例应用；**不得直接迁移既有数据库或重启旧启动器绕过head guard**。原5177/5180未启动或迁移，5180数据指纹不变，旧Mock模式保留。新实例脚本scripts/user-model-preview.ps1仅管理自身；需要用户注册独立账号、填写并主动测试自己的模型。新版功能及迁移未上传GitHub。

实际最终：340后端+2启动器守护/211前端/43浏览器通过，2私人PDF opt-in跳过，类型/构建通过；全部模型自动化为Mock，真实模型请求0，真实MySQL/QA未执行，等待人工验收。不要将旧README“03–06未开发/head0006”等历史说明当作当前本地状态。P0真实MySQL验收及E2/D2仍暂缓。

用户模型预览最终状态补充（2026-10-26）：新站曾成功启动及浏览器显示；最终因D盘从约18.06GB突降至9.998GB触发原10GB保护，正常退出，当前5183/8004不可访问。未降低阈值或再试启动。342后端/守护、211前端、43浏览器通过，2跳过仍为本轮真实自动化结果，不代表当前网站在线或真实模型已验证。新旧数据完整，无真实模型调用；等待释放空间后恢复新站人工验收。详细证据见开发报告最终状态更新。


## 2026-10-26：翻译与笔记统一完整交付（未提交，等待统一人工验收）

唯一验收站 http://127.0.0.3:5183 已实际运行，FastAPI同工作进程提供前端生产构建和API，轻量守护保留原10GB停机门槛。原5177/5180离线保留，不迁移旧库。完整54文件/12,840,357字节联合备份及逐文件SHA256、恢复验证后，从原5180复制1账号/3PDF/7笔记/12关联/6来源块到.cache/user-model-preview/unified，仅副本由0007升级既有0008；源库任务前后表/PDF指纹不变。

复用P2/P3，整合显式离线Mock/个人模型、按请求签名来源和固定Mock QA入口；新增个人模式按账号选择保留，禁止本站消耗开发者默认额度。模型保存不调用，网页主动测试/翻译才请求，DPAPI CurrentUser密文、本人权限/CSRF/CAS、公网HTTPS/IP绑定/无重定向SSRF保护不变。用户明确只在网页自行填写测试；本轮不读取backend/.env，真实模型调用0，不声称course-chat已验证。真实QA仍由06交付，不自建RAG。

本轮全部后端443通过、前端215通过、浏览器48通过/2私人PDF opt-in跳过；类型/生产构建通过，共706通过/2跳过，模型自动化均Mock/受控HTTP/临时SQLite，不等于真实模型/MySQL/QA。实际部署首页/登录/设置静态入口/健康200、未知API404，Chromium登录可见。原P0候选修改与所有已有Git工作保留，无提交推送。详情、操作/修改文件、完整测试边界及统一验收清单见docs/development/final-translation-notes-delivery.md；统一LITERA_HANDOFF追加第53节。


## 2026-10-26：用户最终验收通过，GitHub交付准备（未提交/推送）

用户明确5183统一五项通过。已创建delivery/translation-notes-20261026，HEAD仍947dc3cc6381ce4b19d587762950f381b6e31100。main fetch成功一次，后续全分支Git查询失败，但官方GitHub API补查成功，当前仅main且SHA同上，无新团队提交需要合并；未发布的成员本地工作未知。

本轮补齐Linux可选AES-GCM独立主密钥文件Vault、外部secret override、实际Docker上下文忽略与直接依赖，保留Windows DPAPI/0008字段，无业务迁移或真实密钥转换。测试/构建/公共部署和QA协调文档均已准备；真实QA仍缺，不重写05/06。既有P0候选不动，MySQL未验。

本轮455后端通过（452全量+3新库/离线方言/依赖）、1 POSIX跳过，前端218通过/类型生产构建通过，浏览器65通过/2私人PDF跳过。全为临时SQLite/Mock/受控HTTP；真实Linux Docker/MySQL/QA未执行。构建至独立cache，不覆盖在线dist；5177/5180/5183的数据库/PDF指纹完整性不变，5183健康200，未重启。源代码兼容补丁尚未在旧进程热加载。

交付清单/安全/两组commit与完整PR草案见docs/delivery/github-delivery.md、commit-files.txt、excluded-files.md、PR_DESCRIPTION.md；组员部署与接口见deployment.md、team-integration.md。没有git add/commit/push/merge，不操作Docker/其他项目/Windows设置，不读实际Key，等待用户最终批准发布；完整本机证据追加统一LITERA_HANDOFF第54节。
