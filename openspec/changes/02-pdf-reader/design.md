# Design

## Context

2026-10-16：01及02 A1/A2/B1已通过用户实际验收。B2七类绘制/插入及资产已落地，用户于2026-10-16明确确认整体功能/UI验收通过；4.1–4.6完成，当前24/36，C1/C2及03–06未实施。当前实现与测试以 [B2记录](../../../docs/development/p3-b2.md) 为准，下面A/B1记录属于历史，后续目标段不代表已实施导出。范围见proposal，任务见tasks。

### P3-B2 实际实现

新增0006_reader_assets，保留0005及原业务表。Pillow固定12.0.0校验PNG/JPEG结构、完整解码与尺寸/容量，重新编码规范化朝向及元数据。上传先台账后文件，清理先持久化状态/尝试数；1小时未引用上传、24小时已删对象租约，启动与每60秒扫描，失败显式重试；永久删除接原cleanup_jobs。API、DTO及生产者/消费者见 [API补充](../../../docs/design/api-contracts.md) 和 [数据模型](../../../docs/design/data-model.md)。

PdfDrawingObjects复用PdfPage同一viewport，B1层及保存系统保留。手绘逐帧预览、跨页拆分，10000点/60秒/100000屏幕像素路径上限，pointercancel不留对象。三形状拖动预览、页面内确认；圆按物理尺寸等比，PNG/JPEG/签名按真实比例。签名轻量画布确认后放置，水印只当前页/对象角度。新对象属性就近预览及✓保存/×取消，不用中央模态；对应工具组选择与实时移动/缩放，选中对象临时置前保证重叠控制点可操作，阅读模式穿透文本且只联动列表。

全部13类共用列表、串行CAS/commandId、收据、草稿保护和真实补偿撤销重做。明确ASSET_UNAVAILABLE拒绝后可替换图片用新命令重试；未知结果仍保留原命令核对。清理API202表示失败未完成，管理界面可查询状态并重试。导出租约与导出接口不属于B2。


已逐张检查[15–25截图索引](../../../docs/references/xiaolvjing/reader-reference-index.md)：15整体、16标签菜单、17左导航、18视图、19缩放、23工具、24搜索、25列表。20–22仅说明未来扩展关系。用户要求优先于截图：不照搬视图自由组合、缩略图滑块、核心工具下拉、商业功能或品牌素材。

### 开发前代码与接入缺口（历史快照）

| 接入点 | 已有实现 | 02增量 |
| --- | --- | --- |
| 路由/入口 | router.ts的/reader/:documentId跳回库详情；LibraryPage.readDocument先recordOpen再打开content | 改受保护reader视图及阅读按钮；成功渲染后才记录阅读 |
| 认证 | auth.ts/api.ts/main.ts与current_session/require_csrf已有Cookie/Origin/CSRF和401事件 | 复用全部机制；GET内容无需CSRF，写入必须携带；退出释放私有状态 |
| PDF | documents.py校验owner/有效文献，200/单Range206，非法/多Range416；有Length/Range响应头，无HEAD/ETag/If-Range专用实现 | 同源URL加载，不用JSON api<T>读字节，不依赖不存在的缓存协议 |
| 页数 | page_count当前null；requirements.txt已有pypdf==6.20.1，上传PdfReader校验非加密/至少一页但未存页数 | 优先复用现有库按需校验/填充真实物理页数，独立于05 |
| 进度 | GET/PUT progress、reading-history已有；PUT {}写服务器lastReadAt及独立version；非空pageNumber/zoom503 | 扩展原表/接口；page_number nullable整数，zoom nullable VARCHAR(20)，DTO转float |
| 生命周期 | 0001_auth→0002_documents→0003_library；无annotations/资产/导出 | 增量迁移，接原cleanup_jobs失败/重试链，不重建现表 |
| UI/类型 | OverflowText、Element Plus Icons、#9B0000主题已有；ReaderContext等只有文档 | 复用组件与主题；建立真正公共类型/事件 |

保留账号、文献ID、题录、原文件/存储键、旧进度/历史。01专项MySQL证据仍按历史交接跟踪，不以SQLite替代。

### P3-A1实际实现（2026-10-15）

1.1–1.6已实现，详见[开发记录](../../../docs/development/p3-a1.md)。pdfjs-dist精确6.4.299，真实module Worker同包Vite构建，CMap/标准字体/WASM/ICC同源开发/生产资源；共享PdfPage使用Canvas/TextLayer，ReaderPage负责三视图/页码/文献切换，ReaderPanel负责折叠/窄屏dialog，reader/state保留轻量会话状态及坐标适配。前述占位路由与浏览器预览已替换，后端内容/权限契约复用，无新增迁移或业务API。

A1固定scale=1、左右框架初值左240/右320px，尚无交互缩放、调宽、缩略图/大纲/搜索或真实进度；库点击不提前recordOpen。三工具组及二级栏只提供开发中UI，未实现任何标注/插入/保存/导出或03–06业务。后文描述包含A2及之后的目标设计，不代表全部完成。

### P3-A1交互补充（最新用户授权）

本轮属于A1补充，保持6/36和六阶段结构，不启动A2。WorkspaceTabs由库/阅读器共同使用现有会话store，统一文献管理入口/单个关闭，路由活动态决定高亮；库中标题进阅读器，详情/原件下载直接展示，其余在更多。退出/换用户清标签，不缓存PDF实例；软删除当前列表文献移除对应共享标签。

阅读组默认隐藏二级栏；布局变更保存页内锚点/滚动位置和页码，完成后恢复。搜索/列表/下载/导出为统一图标及浅色Tooltip。左导航复用库startPointerResize指针捕获，180–320px调宽且收起恢复，窄屏保留原生dialog。PdfPage只在进入可见范围且尚无完整帧时渲染，临时Canvas完成后再提交，远处仍释放；无中央渲染文字，失败保持原错误/重试。

首个完整页面ready按本次文献加载generation触发一次原recordOpen→PUT progress {}，服务器写lastReadAt，不提交页码/缩放。离开/切文献等待已发写入完成（8秒超时），避免返回库查询竞态；失败显示可重试提示并记录状态码/code/requestId，手动重试只写真实接口。此项按用户本轮明确要求从A2提前补齐打开子集，不提前实现完整进度。

## Goals / Non-Goals

**Goals:** 三种视图共享渲染；坐标跨缩放/旋转一致；保存/撤销/导出快照一致；多标签资源有界；公共接口松耦合。

**Non-Goals:** 双页连续、布局与转换自由组合、缩略图独立缩放、独立书签工具、OCR、PDF正文改写、表单填写/测量/复杂绘图、证书数字签署、编辑任意第三方原生批注。03–06的UI、机器人、供应商调用与表全部不实现。原文件内置内容/批注正常展示；本模块批注列表与编辑仅管理Litera对象。

## Decisions

### 1. 布局与组件边界

品牌导航（阅读器48px、文献库仍52px）和40px文献标签栏→40px主工具栏→40px独立二级工具栏→左导航/中央PDF/右辅助面板。主栏依次展示“阅读、批注、形状、插入”，默认阅读并隐藏二级栏，其他组显示对应二级工具；一个视图选择器，另有页码、缩放、搜索、列表、原件下载/带批注导出。窄屏四组允许横向滚动，不合并为一个下拉。

左侧仅缩略图/原生大纲，默认240px、180–320px；右侧仅搜索/批注列表，默认360px、280–520px，一次一个。PDF目标最小480px，不足时面板变覆盖抽屉；折叠释放空间，键盘separator可调宽，抽屉有焦点约束/Escape/恢复。面板宽度为UI初值，可随验证调整。白灰与#9B0000，长标题用统一浅色Tooltip。

ReaderWorkspace管理标签/上下文，ViewHost决定页面集合，共享PdfPage负责各层。A1先建轻量标签容器和文献切换生命周期；C2补齐批量关闭/溢出管理，不能等C才考虑B的数据隔离。没有翻译/笔记/AI占位面板或功能轨。

### 2. PDF.js与渲染层

A1选择与当前Vue/Vite/Node兼容的pdfjs-dist精确版本并锁定；本轮不选虚构版本、不安装。主线程、Worker、文本层样式、CMap/标准字体资源同包同版本，由Vite本地打包同源发布；不用CDN混配或静默fake worker。生产构建必须验证Worker与中英文字体。[PDF.js官方FAQ](https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions)说明版本匹配和整篇Canvas内存成本。

Canvas绘原页面；text layer提供可选文本/搜索范围；PDF原生annotation/link layer保留安全内部链接，限制不可信动作；自有交互层负责命中/选区/拖动，覆盖层绘Litera对象。选择工具与绘制工具显式互斥，不用对象层吞掉普通文本选择。所有层共用同一viewport（CropBox/UserUnit/源文件固有Rotate）。禁止并发render到同一Canvas。

同源content URL沿用HttpOnly Cookie。401接已有失效事件并取消/清空私有状态；404显示不可用；416取消Range后最多一次完整读取回退，仍失败显示重试/返回；损坏/不支持加密不记成功阅读。退出/切换的旧错误不能污染新文献。

### 3. 三种视图及缩放

ViewMode=continuous|single|spread，默认continuous。连续为纵向虚拟列表；single只显示一页；spread按(1,2)/(3,4)分组、翻页切组，末页奇数单独显示，无封面特例/纵向连续翻组。双页currentPage可为组内第二页；下一组按组首+2。连续当前页取视口中心最近页，双页取最后显式导航/交互页。目录/搜索/批注定位先设目标页/组，等待挂载再定位页内位置。

切视图保留物理1-based页码和局部中心锚点；custom倍率保持，fit重新计算。双页窄屏允许容器横向滚动及组切换，不重叠、不生成第四模式。方向键仅PDF视口聚焦且非输入/编辑状态时生效，single/spread切页/组，continuous自然滚动。

ZoomMode=custom|fit-width|fit-height。API倍率0.5–5（100%=1），UI50%–500%；预设50/75/100/125/150/200/300/400/500%，加减25个百分点，手输可小数；非数保留并提示，超界clamp并提示。自身尺寸=适应宽度，页面尺寸=适应高度。双页fit-width计算两页总宽+间距，fit-height按最大页高；fit也受0.5–5边界，无法容纳时滚动，不偷降至50%以下。

Ctrl+wheel仅PDF容器的非passive监听接管；外部区域保留浏览器行为。手动缩放切custom，逆变换保存鼠标处PDF点（无鼠标取中心），更新后恢复屏幕位置；快速缩放只采纳最新generation，稳定后清晰重绘。ResizeObserver监听实际阅读容器，fit随面板/窗宽重算并避免循环布局。

### 4. 坐标、加载与内存

Canvas数量、内存/缓存/并发预算及长文压力样本等数值均为初始工程预算，可在开发中依据真实测试调整并记录原因，不作为固定产品约束或提前优化的验收门槛。优先实现正确、稳定的核心阅读功能；按需加载、必要取消/释放及基本资源保护仍须落实，分块绘制、复杂缓存/索引等优化仅在实测需要时采用。权限隔离、数据一致性和错误恢复要求保持不变，不能因预算调整或延后优化而削弱。

持久坐标相对未旋转可见CropBox左上角，x/y/w/h在0–1且不越界；先逆viewport得PDF用户坐标，再处理CropBox偏移、UserUnit和顶/底原点。恢复/导出使用逆过程。多页文本为逐页矩形数组；笔迹为页内归一化点列；圆在PDF物理尺寸宽高相等。字体/笔宽存PDF point。DPR只影响Canvas backing store，不重复作用坐标。

初始工程预算（实施时测量并记录机器/样本）：活动PDF实例最多1；页面Canvas可见+邻近最多6张、单张16M像素、总backing store192MiB；缩略图最多12张/16MiB。按宽×高×4估算，实测需要时降低DPR或采用分块绘制并明确清晰度状态，逻辑缩放仍可500%；禁止巨图无界分配。虚拟DOM保留尺寸占位。缩略图只渲染可见附近，无独立缩放滑块。

文本按页提取（初始并发预算2），索引缓存初始预算32MiB；实测需要时采用有界分段扫描/淘汰，显示进度，结果不能静默截断。全文搜索不能要求全部Canvas完成。

标签仅保留页码/锚点、zoomMode/zoom、viewMode、面板状态、草稿/队列等轻量信息，不长期保留整篇渲染。切换先递增generation并清选区、取消renderTask/文本索引/内容请求，等待取消后cleanup页面和销毁loadingTask/document；释放Canvas尺寸、ImageBitmap、ObjectURL、监听器及所选版本的Worker资源。旧响应仍以documentId+contextRevision+generation拒绝。保存回执单独按documentId+commandId/version归属，不能因切换丢弃真正成功的写入。

### 5. 导航、文本搜索与进度

原生Outline支持层级折叠/内部命名目标，无Outline空状态，坏目标给反馈。搜索真实PDF.js文本，规范化后保留字符→text layer范围映射，支持跨text item匹配。大小写可选，全词规则为拉丁字母数字词边界、其他文字按Unicode词分段（样本固定规则）；按物理页/页内顺序，上/下匹配可循环并显示序号。搜索高亮不是标注。空词清结果，无结果/全篇无文本分别提示，混合扫描仅搜索文本页，无OCR/05依赖。

扩展原reading_progress新增nullable view_mode/zoom_mode，旧null默认continuous/fit-width；zoom继续存倍率字符串，对外number。旧PUT {}及仅含null的旧字段请求保持只记打开，不清状态；新状态写必须version（未读0），省略保持，新增设置显式null拒绝422。服务端用现有pypdf验证页数，不信任客户端pageCount，不改变题录version。

加载先GET进度并恢复，首次目标页成功渲染后才CAS写当前页/设置及服务器lastReadAt，失败加载不更新；01库阅读按钮不再提前recordOpen。页/设置稳定1秒防抖、持续变化最多5秒一次，单文献串行保存；离开主动flush，失败提示/重试，不仅依赖unload。409读最新并保留本地待存状态，用户选载入服务端或基于新version明确保存本地，不能静默覆盖他端。首目标页成功时recordOpen=true，同事务更新documents/reading_progress.last_read_at；后续普通进度保存recordOpen=false不更新最近打开时间；GET/下载/导出不更新最近阅读。旧请求缺省recordOpen=true兼容。

### 6. 对象类型与操作

AnnotationType共13类：highlight、underline、squiggly、strikeout、comment、freeText、ink、rectangle、circle、ellipse、signature、watermark、image。独立bookmark从旧规划移除，无旧标注数据需迁移。highlight绑定真实文本矩形，ink为自由手绘笔迹，可用于有文本或扫描页。下划线/波浪线/删除线同样必须真实选区。

对象数量以6类B1文本批注+1类手绘+3类形状+3类插入=13为准。2026-10-16取消独立荧光笔；原marker只存在于目标设计，取消时API/前端类型仅六类（本轮B2已扩至13类），未为此改库或转换数据。手绘留待B2 4.1，高亮继续依赖真实文本选区。

AnnotationDTO保留id/documentId/type/pageNumber/position/selectedText/content/color/version/时间，增加schemaVersion=1、geometry、style、assetId、zIndex。position为文本逐页锚点；geometry为box/points/anchor判别联合；服务端按type验证所有子页/边界，拒绝未知字段/任意HTML或JS。style白名单stroke/fill/opacity/lineWidth/fontSize等，#RRGGBB自定义与透明度分离。类型不可变，文本重选建新对象；box/path可合法移动缩放。

| 对象 | 创建/定位 | 编辑及保存规则 |
| --- | --- | --- |
| 四种文本标记 | 选择真实文本创建多矩形 | 颜色/透明度可改；锚定原文不自由拖移；重建/删除可撤销 |
| 注释 | 页点或文本选区，纯文本内容 | 页点可移动；文本锚点不拖移；保存内容/位置，与04笔记独立 |
| 自由文本 | 点击/框选并输入纯文本 | 移动、改框、字号/颜色；换行按框，导出验证字体与可见内容 |
| 手绘 | 指针采样页内点列 | 颜色/笔宽/透明度、整对象移动缩放；跨页拆对象，pointercancel不留半条 |
| 矩形/圆/椭圆 | 页内拖动box | 边框、填充可无、线宽；圆等比，另两类自由缩放，限页内 |
| 签名 | 手写确认后放置，或本地PNG/JPEG签名图 | 单页视觉对象，移动/等比缩放；无签名库/证书签章 |
| 水印 | 输入纯文本，当前页预览确认 | 内容、角度、透明度、字号、box移动/尺寸；首版仅当前页，无全篇批量 |
| 图片 | 本地PNG/JPEG真实解码后放置 | 保持纵横比移动/改大小，存本篇私有assetId；不接受远程URL/SVG/任意附件 |

所有对象可选择、编辑属性、删除；橡皮擦为命中后删除整个Litera对象，不擦原PDF或局部分割笔迹。删除键只在对象选中且阅读器聚焦时生效。右侧列表覆盖本篇全部Litera对象及注释/插入，展示页/类型/摘要；按页位置或创建时间排序，按类型/颜色筛选，点击定位；编辑/删除同步列表与未保存状态。搜索/列表共用右区，分别保留本篇状态。

2026-10-16已验收的P3-B1局部编辑优化覆盖历史中央编辑窗行为：注释在原列表卡片内编辑；页面图标点击仅定位卡片。自由文本仅在批注组单击显示轻量边框/八方向控制点，阅读组单击只联动列表、双击切批注组；双击及新建在原页面使用同viewport变换的textarea输入，附近复用颜色/透明度/字号控件；新建和页面双击不自动滚动离开点击位置，列表编辑可跳转对应页。尺寸与字号独立，保留原geometry.box.rect和style.fontSize，无接口/数据库变化。卡片/页面统一✓保存与×取消；未提交编辑阻止切文献/关闭面板/替换编辑对象，保存失败保留已进入原队列的草稿，取消已提交操作先核对结果再用补偿撤销恢复。窄屏批注列表沿用原侧面板但为非模态，无背景遮罩；搜索面板维持原行为。高亮等四类文字标记仍沿用原属性编辑器。

### 7. 持久化、撤销与增量迁移

新增annotations：owner/document外键、type/schemaVersion、position/geometry/style JSON、文本、asset_id/z_index/version/时间；索引owner/document/page及document/updated。新增document_reader_state保存annotationRevision，与题录/progress/contextRevision独立，每次对象变更同事务递增。reader_assets保存owner/document、私有键、mime/hash/像素尺寸/状态，只能受保护读取；命令收据保存幂等结果。不提前创建03–06表。

初始限额：单资产5MiB/20M解码像素、本篇资产50MiB、单对象1MiB JSON/10k点/20k文本、本篇10k对象；超限413/422不截断，可配置后实测。未引用上传1小时清理；已删对象资产延迟24小时回收以支持撤销，导出快照引用加租约；到期后撤销涉及资产时明确不可恢复。新增资产清理须有幂等重试和启动扫描，不留下孤儿。

写入commandId+baseRevision（文献标注集CAS）及现有对象version，服务端事务提交对象/集合版本/收据；超时按commandId查询/幂等重试。客户端每文献串行队列，区分草稿/发送中/确认/失败，1秒自动保存，显式保存flush。失败保留草稿；关闭提供保存并关闭/放弃未确认修改/取消。结果未知的在途命令先查收据，不直接当未写入放弃。

每文献撤销栈最多100条语义命令，一次拖动一条；不含缩放/进度，不跨刷新保留（刷新恢复已存对象）。未发命令可移出队列；在途等结果；已确认undo发带最新CAS的补偿命令，删除可通过受控restore恢复原ID，redo用新commandId。新编辑清redo，失败暂停队列保留栈；409读取新版后由用户决定重放/放弃，重载或他端更新清失效历史并说明。Ctrl+Z/Y仅阅读器非input/textarea/contenteditable且无其他弹窗焦点时接管，输入框使用自身撤销。收据24小时，过期未知结果先重新核对集合，禁止盲重发。

迁移分A2扩展原progress、B1标注集/收据、B2资产、C1必要导出作业；编号实施时串行协调。A2已新增0004_reader_progress，其余迁移留对应阶段。nullable/default兼容旧记录与PUT {}；隔离SQLite+真实MySQL验证从0003升级保留数据/约束。软删屏蔽所有访问但保留数据，恢复原ID；永久清理覆盖对象/资产/收据/导出临时产物，失败进入原cleanup_jobs可重试。写入/导出与清理以文献锁/不可恢复标记协调；回退禁reader并保留数据，不以downgrade删标注。

### 8. 原件下载与带批注导出（C1再定具体方案）

原件GET content?download=true，字节哈希与上传一致。导出包含本人本篇服务器已保存的全部13类对象；存在未保存内容时必须明确提示，先保存并确认成功，或由用户明确选择上次已保存版本。提交expectedAnnotationRevision，冲突409重新选择；一致性事务复制源fileHash、对象/样式/资产引用，后续编辑不改变快照，不能混多个版本。

| 路线/技术候选 | 能力与取舍 | C1验证重点 |
| --- | --- | --- |
| 标准PDF Annotation+appearance | 文本四类可映射Highlight/Underline/Squiggly/StrikeOut；comment→Text、freeText→FreeText、ink→Ink、矩形→Square、圆/椭圆→Circle；签名/图片可能Stamp | 外观流、QuadPoints、透明度、中文、Rotate/CropBox；标准对象存在不保证各阅读器都可编辑 |
| 扁平化页内容叠加 | 文字/路径/形状/图像/水印写入页面，通常只能看；保留原页矢量/文本，避免整页截图 | 注释正文以可见说明框或带页码定位的附注页保留，不能只剩图标；字体/换行/Z序 |
| 混合 | 常见对象原生且带外观，复杂对象扁平化 | 每类型能力矩阵，不漏对象或重复绘制 |
| 现有pypdf | 优先评估复用注释写入/叠加PDF，不当万能渲染排版器；必要配ReportLab生成文字/矢量叠加 | 锁定版本真实API、外观/字体限制；新增库仅实施时评估 |
| PyMuPDF备选 | 注释、绘制及烘焙能力候选 | 精确版本、平台包、字体及许可适配审阅后再选；目前未安装/未决定 |

后续C1导出验收清单共13类（尚未实施导出）：

| 分组 | 对象 | 数量 |
| --- | --- | --- |
| B1文本批注 | highlight、underline、squiggly、strikeout、comment、freeText | 6 |
| 自由绘制 | ink | 1 |
| 形状 | rectangle、circle、ellipse | 3 |
| 插入 | signature、watermark、image | 3 |

每类均需独立验证外观、位置、颜色/透明度及必要正文；不以少数类型成功替代13类完整矩阵。

最低验收是第三方可见（含注释正文）；第三方继续编辑单列能力，不能承诺全部原生可编辑。C1技术验证后形成ADR，冻结扁平化/混合/原生路线、库与同步/异步协议。依据：[pypdf注释](https://pypdf.readthedocs.io/en/stable/user/adding-pdf-annotations.html)、[水印与叠加](https://pypdf.readthedocs.io/en/stable/user/add-watermark.html)、[PyMuPDF注释](https://pymupdf.readthedocs.io/en/latest/annot.html)、[bake](https://pymupdf.readthedocs.io/en/latest/document.html#Document.bake)、[许可说明](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)。能力资料不能替代锁定版本样本实验。PyMuPDF bake会丢失注释的隐藏正文等非外观数据，因此不能直接烘焙图标就声称已保留注释；必须先把正文做成可见说明或附注。

服务端受保护写请求创建快照，输出到私有临时文件再受保护流式下载，避免整个产物长期BytesIO；库本身可能整文件驻留，仍须测峰值。初始预算并发1/进程、60秒超时、子进程512MiB、产物200MiB，可配置实测；超限/压缩炸弹/超时要终止工作进程并失败，不阻塞API、不泄漏半成品。成功发送结束、失败、取消、TTL1小时及启动扫描均清临时文件。若异步，C1冻结创建/状态/下载/取消API和审计，不借用03–06队列。

创建/状态/下载逐次校验owner/有效文献/资产，软删及永久清理取消或屏蔽在途导出，流开始前复验；已发字节无法撤回，后续请求仍拒绝。浏览器退出不保证服务端停止，服务端必须超时清理。原存储只读，比较导出前后原hash；导出不记阅读。

至少用Windows Edge PDF与Adobe Acrobat Reader两种独立阅读器逐类型验证可见性、中文/透明度/注释正文/图片和旋转位置，记录版本；不能只在Litera/PDF.js自测。自动结构检查/文本可读性/渲染对比补充人工跨阅读器证据。

### 9. 公共上下文与成员边界

ReaderContext保持documentId、pageNumber、selectedText、SelectionPosition[]|null、annotationId|null、contextRevision。物理1-based页码、坐标见本设计；有文本选区时ReaderContext.pageNumber取选区起始页，无选区时取当前阅读页，UI当前页状态另由视图保持。文献/页/选区变化递增工作区单调revision（含A→B→A），清空选区发空文本/null，销毁发context-cleared；context-change/selection-change/document-change发布真实快照，响应用documentId+revision验证。

02拥有公共types、可取消订阅事件和导航adapter；03消费选区，04消费NoteDraft来源，05复用documentId/物理页契约，06消费上下文并提供带提取版本引用。引用导航只接受本人有效文献/页码，chunk/extractionVersion由真实来源模块验证，未接入返回unavailable，不制造chunk/调用服务。保留NoteDraft/Citation类型，不实现save-note UI或业务表；上下文不是权限凭证，后端每次校验owner/关联。PDF本地搜索不读05文本API。没有翻译面板/笔记页/AI聊天/机器人/模拟业务。

## Risks / Trade-offs

- 坐标：混合页尺寸、CropBox偏移、90/180/270度、DPR1/2、多页选区往返测试，正常DPR覆盖误差目标≤1 CSS px。
- PDF.js内部接口/字体/浏览器：锁版本并测生产Worker，不只开发服务。
- 保存超时/他端冲突：集合CAS、幂等收据和补偿undo一起测，不能只前端数组undo。
- 高倍Canvas/长文索引/图像/导出内存：有界预算与进程隔离，超限明确反馈、不静默漏页/对象。
- 导出：中文字体、注释正文、复杂样式与许可是C1决策门槛，13类第三方可见才能通过。

### 10. 验收样本与测量记录

功能样本覆盖：1页、7页奇数；长文压力测试以1000页为初始样本建议（文件仍受现有50MiB上传配置限制）、中英文/无Outline/多级Outline、全扫描/混合文本、混合页尺寸/CropBox偏移/固有90度页、多页选区、损坏文件及损坏图像。长文可用无敏感内容生成样本，不提交用户私有文献。浏览器覆盖生产Chromium/Edge与Firefox，视口1366×768/1920×1080/390×844、DPR1/2；跨阅读器导出按第8节独立验证。记录CPU/内存/浏览器版本、首屏/搜索/切换耗时、JS heap/Canvas估算峰值及10标签反复切换关闭后基线。长文页数、标签数量及性能测量规模按开发阶段和真实测试调整；详细压力验证集中在C2，早期先验证核心正确性、稳定性及必要资源释放，不提前实施无实测依据的优化。根据结果调整预算和延迟门槛，不虚构通过结果。

## Migration Plan

按A1→A2→B1→B2→C1→C2实施，详见tasks。A1/A2/B1已通过用户实际验收，B2开发及用户整体功能/UI验收完成，4.1–4.6已勾选，当前24/36；下一阶段P3-C1（5.1–5.6）尚未启动。迁移链至0006_reader_assets，保留原用户/题录/PDF/批注/进度；自动化使用隔离SQLite，MySQL仅离线DDL，专项MySQL及旧数据升级仍待独立证据。未运行Compose或业务迁移，不修改03–06状态，不提交或归档，本阶段已验收，等待新会话指令。

## Open Questions

用户已确认首版产品约束：水印仅作用于当前页；签名属于视觉对象，不涉及数字证书；撤销/重做历史不要求跨刷新保留，但已保存批注必须持久化；带批注PDF导出使用服务器已保存的版本快照，存在未保存内容时明确提示。这些约束不再是待确认项。

工程决策留到对应阶段：A1锁PDF.js/浏览器样本；B2实测对象资产限额；C1凭全类型样本定导出库/协议/字体。用户可补充目标电脑、最大页数/并发、第三方阅读器版本；当前数字为待测工程预算，不是已达成性能。50%–500%、三种模式及无03–06 UI已确定。

## P3-A2实施说明（历史，2026-10-15）

实现与测试范围见[开发记录](../../../docs/development/p3-a2.md)。所有A1布局/三视图/标签排序沿用，加入独立zoom/search/progress/context小模块；共享PdfPage接受逻辑scale/真实页尺寸，Canvas DPR预算与层坐标分开。显式跳页优先于异步fit锚点恢复，路由切换以loadedDocumentId+generation拒绝旧文献进度/选区/搜索。

搜索逐页提取且不保留全篇文本索引；NFKC、空白统一，保留字符→text item/offset映射；全词按浏览器Intl.Segmenter('und', word) Unicode词边界（英文数字按整词，中文按词分段）。单页50万UTF-16字符、全文2万匹配为初始资源保护，超限明确报错要求更具体查询，不静默截断或假报完整结果；缓存/压力优化留C2。文本与缩略图处理generation取消，无法取消的单个PDF.js提取完成后丢弃旧结果。

0004迁移只加view_mode/zoom_mode可空列；服务端用文献行锁及progress FOR UPDATE当前读避免MySQL重复读快照导致CAS失效。页数来自pypdf，缓存不改题录version。旧PUT {}及旧null pageNumber/zoom兼容，新状态写必须独立version。前端1秒防抖/5秒最大等待、串行CAS、8秒超时、离开flush；失败/冲突保留用户与文献隔离的sessionStorage设置草稿，用户明确处理后再离开；不存PDF/文本。ctx真实选区包含每页textQuote与归一化矩形，订阅/清理接口已落地，完整引用导航仍C2。

本节记录A2当时的边界，不含持久批注；其后B1已完成并验收，绘制/插入/导出及03–06仍未实现。MySQL仅离线DDL，真实专项集成仍需独立证据。

## P3-A2 UI补充（当前尺寸，2026-10-15）

用户已在Docker实际体验核心功能并确认整体符合预期。本轮只做前端UI补充：阅读器品牌/标签/主栏/二级栏48/40/40/40px，阅读组隐藏二级栏，移除Footer；品牌20px和基础UI12px使用全局Token，标题层级保留，库品牌栏仍52px。PDF四周padding与页间gap统一12px，由同一常量驱动CSS/fit/导航偏移；fit扣两侧24px、双页加12px间距/取最高页，读取实际容器client尺寸，不重复扣导航高度。PDF.js全局.spread的3.5px双侧margin在本地集合覆盖为0，避免7px额外横向溢出，真正超宽仍滚动并使用白灰细滚动条。缩放/大纲采用同包SVG Chevron；鼠标操作不显示阅读区整圈焦点框，Tab进入保留局部focus-visible提示，输入框方向键不接管。

本节覆盖前文历史尺寸/间距，不变更架构、后端、进度队列/接口及B/C边界。测试及手动验收见[UI补充记录](../../../docs/development/p3-a2-ux.md)。当时12/36；后续B1验收时18/36，未新增阶段或任务编号。

## P3-B1实际实现（2026-10-15）

六类文本对象按既定模型实现，0005_annotations增量接0004；annotations保存受控恢复墓碑，document_reader_state及annotation_command_receipts维护独立集合CAS/幂等。Document行锁串行首次写入并与软删/清理协调，当前读校验对象/集合版本；同事务提交，失败不部分写。软删保留、恢复原ID，永久清理新增三表纳入原失败/重试作业。无资产表、无03–06表。

PdfPage在原reader-object-layer挂PdfAnnotations独立SVG，同viewport正逆变换；四类标记复用context.ts真实多行/多页rects，注释支持文本或页点，自由文本使用box。最终注释在右侧卡片内编辑；自由文本阅读组单击只联动列表，双击切批注组原位输入，批注组可实时拖动/八方向改框，字号独立。文本标记属性保留紧凑dialog；注释/自由文本不使用中央弹窗，统一✓保存/×取消。颜色、透明度、字号及几何沿用原模型；顶部拖动条35%不透明度、左侧约3屏幕px留白，单/双击判定避免侧栏重排丢失第二次命中。B1当时B2工具尚未启用；本轮B2交付见前文。

reader/annotations.ts独立串行队列：1秒自动保存、8秒超时、准备请求先落本地草稿；超时/刷新先查收据，原命令原ID重试，后续依赖失败即暂停。100条语义撤销历史，已存undo/redo提交真实补偿；在途先等确认。冲突不自动重放覆盖服务端，提供草稿导出/显式载入服务端并保留可导出备份，重新加载清无效历史。路由/活动标签关闭flush失败阻止静默离开，可显式保留草稿后返回库，编辑中阻止离开，浏览器关闭提示；输入自身快捷键保留。独立于progress保存队列。

AnnotationList复用右区，位置/时间排序、类型/颜色筛选、摘要/时间、列表→页点及对象→列表选中，搜索切换保持位置；仅管理Litera对象、不依赖04。测试使用真实上传、PDF.js、隔离SQLite API；旋转CropBox跨倍率几何一致，DOM字体行框取整的误差按PDF point记录。MySQL仅增量DDL离线编译，用户Docker实际功能/UI已验收，真实MySQL专项集成仍未运行/未提供证据；B1正式交付后停止，等待新会话。

按照用户最新指示，平台不提供手动页面旋转或视图旋转状态，历史“视图旋转”目标不属于交付范围。PDF.js继续读取源文件固有Rotate/CropBox以正确显示原文。完整帧提交TextLayer时同时保留PDF.js的data-main-rotation属性，页容器提供--scale-round-x/y尺寸变量，确保源文件自带朝向下选区与Canvas一致，不改变原PDF。

## P3-B1交互修复（2026-10-16）

本次仅完善B1，仍18/36。创建直接读取手势结束/点击工具时的原生Range，ReaderContext仍是对外快照；裁切元素/Text边界，记录每页UTF-16 textRanges(item/start/end)。禁止TextLayer原生HTML文字拖放，新手势可重选旧选区，保留复制及Shift扩选。逐页将Rect逆变换到未旋转CropBox坐标，以真实PDF宽高判断同行、最多0.55行高间隙，不跨行/栏；已有分段对象仅显示时合并，不重写数据库。Rect可选baseline是字体升部占完整行框比例（0–1），新选区按浏览器字体metrics记录、合并时重算；旧对象缺省0.8。下划线/删除线按基线定位并限制线宽/波幅，SVG二次贝塞尔绘平滑波浪。

文本SVG对象鼠标穿透，在PdfPage以结束后的单击命中测试选择，拖选不触发编辑；阅读组不画选框，创建后清选中，空白/Esc/阅读退出编辑。页点气泡的尾尖固定原坐标，屏幕尺寸恒定并在靠边时翻转，使用原anchor模型；批注组自由文本/气泡可直接拖动，局部preview随pointermove，pointerup一条edit，Esc/pointercancel/换文献/换倍率/卸载清预览。失败位置由原保存队列保留草稿，可重试/补偿撤销。

字体比例和字符范围仅为原JSON中可选字段，旧JSON缺省不输出null，旧墓碑可恢复；不改schemaVersion、不新增迁移。API/认证/CAS/收据/进度机制沿用。成功反馈只在真实写入确认后、PDF区域顶部居中显示1秒绿色对号，单实例且不接收鼠标；失败/冲突保留原明确提示。工具语义SVG为项目自绘，无新依赖。详细证据及Windows手动验收见开发记录末节。
