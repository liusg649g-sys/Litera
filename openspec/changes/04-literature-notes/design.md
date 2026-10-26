# Design

## Context（P3-A历史背景）

动机见proposal。现有笔记仅文档规划，阅读器已有共享ReaderPanel、认证api及路由草稿守卫，未安装富文本编辑器。P2和P0及未提交成果须保留。5177使用持久SQLite；启动器会alembic upgrade head，本轮禁止重启或迁移该真实库。

## P3-A Goals / Non-Goals

**Goals:** notes本体独立于文献；M:N关联、明确删除语义、串行CAS自动保存、失败/冲突不丢草稿、侧栏与翻译兼容、隔离迁移/浏览器证据。

**Non-Goals:** 富HTML/Markdown渲染、全文检索、来源内容插入、AI/模型调用、共编/分享，不提前开发P3-B/P3-C。

## Decisions

1. 两表增量：notes(id UUID PK,owner_id FK users,title String200,content Text/MEDIUMTEXT,content_format='plain-text',version int,source_schema_version=1,sources JSON空数组,created_at/updated_at fsp6)。note_documents(note_id FK notes CASCADE,document_id FK documents CASCADE,owner_id FK users,created_at)，复合PK(note_id,document_id)及owner/document索引。应用给sources显式空数组，不用不兼容MySQL JSON server default。不在notes放document_id。
2. 关联始终检查note/doc双端owner与文献有效状态，DTO只显示active owned文献；个人笔记列表包含无关联笔记。文献软删仅使其当前文献入口/关系不可用，个人笔记本体可读，恢复重现关联；永久删除文献仅FK级联关系，正文保留。删除note才删本体与所有关系，UI明确确认，解除关联另设操作。旧清理代码不需写notes表。
3. 标题1–200字符，空编辑显示默认未命名；正文0–100000字符安全纯文本(input/textarea+转义输出)，不新增依赖。P3-A不接受客户端sources/owner，保留sourceSchemaVersion/sources响应供后续可信NoteDraft适配，未来内容来源与文献关联不是同一概念。
4. API前缀/api/v1：GET /notes/config认证后返回available/contentMaxLength/titleMaxLength/contentFormat，只读检查必要表/列，未迁移时available=false。其它笔记路由缺schema返回503 NOTES_NOT_READY。老API无路由返回404，前端明确“笔记尚未部署”，禁用CRUD，不触发重置/迁移。
5. GET /notes?documentId?&page=1&pageSize=20返回{items,page,pageSize,total}，列表NoteSummary含id/title/contentFormat/version/sourceSchemaVersion/createdAt/updatedAt/documents[{id,title}]，无全文搜索；GET /notes/{id}详情再加content/sources。
6. POST /notes {id客户端UUID,title,content,documentId?}，201创建，重复同id同内容初始关联200返回同一笔记；内容已变则409不覆写。PATCH /notes/{id} {version,title?,content?}以owner/id/version原子CAS，精确内容重放返回当前不加版本；不同内容旧版本409，返回明确NOTE_VERSION_CONFLICT。DELETE /notes/{id}?version=N CAS后204，越权/不存在404。PUT或DELETE /notes/{id}/documents/{docId}无body，幂等set，均200详情；关系变动不改正文版本。不可把另用户UUID当所有权凭据。
7. Vue notes API/controller与NotesPanel常驻ReaderPage，documentId prop由路由传入，不把ReaderContext选区事件当切文献。800ms稳定自动保存，真实单笔记串行，编辑期间只发最新快照；保存中/已保存/失败/冲突明确。失败不循环重试，显式重试沿原baseVersion；409保留输入，显式确认载入服务端版本，不静默换version覆盖。sessionStorage按user/note隔离备份脏草稿，刷新/本人重登录恢复，服务端版本变化显示冲突；退出仅清内存/取消旧scope，不自动删失败草稿或让他人显示它。成功保存/明确丢弃才清对应草稿，quota失败明确提示。
8. 暴露toggle/beforeLeave:Promise<boolean>给ReaderPage，路由/标签导航先flush，保存失败阻止离开，beforeunload提示未保存；收起仅隐藏、不清编辑。独立翻译与笔记布局宽屏并列/不足时抽屉或分区，PDF保持可读，无论开关哪一栏不重置另一栏。

## Risks / Trade-offs

- [越权/伪来源] → 所有API认证、写Origin/CSRF，双端owner，extra字段禁止，P3-A仅手工来源。
- [并发覆盖/重复提交] → 客户端创建UUID、CAS、链接唯一PK/幂等、服务端事务锁与提交后refresh；客户端串行与epoch阻旧响应。
- [草稿丢失] → 失败保留+账号隔离sessionStorage+导航守卫；冲突只显式确认重新载入，草稿是浏览器会话副本而非云同步/备份。
- [Vite自动加载新UI但旧API未部署] → config404/availablefalse友好提示，禁CRUD；不可因此重启5177。独立人工预览如提供须用新数据目录/端口和不同loopback主机隔离Cookie。
- [MySQL部分DDL/旧程序回退] → 不承诺事务回滚；失败保留现场，禁止删表/盲重试/降级。回退应用须保留0007迁移文件及新表，禁用笔记入口，避免旧迁移目录不认识已升head。

## Migration Plan

0007_literature_notes down_revision=0006_reader_assets，只create两新表/索引/FK，无旧表ALTER、数据回填、旧数据删除或文件操作。SQLite启用FK、DateTime保微秒；MySQL使用InnoDB现有约定、DATETIME(fsp=6)/MEDIUMTEXT/JSON。先独立临时SQLite测试从0006保有旧账号/文献/批注/PDF升级并比较旧行/文件；重复upgrade幂等；MySQL离线DDL检查不标真实MySQL通过。

真实迁移需用户另行确认后：核对旧head/清理候选/空间与停机计划，正常停止5177、联合备份整个.cache/local-site（DB/WAL/SHM/PDF/图片/会话/日志，禁止覆盖），比较路径/大小/SHA256并只读检查副本完整性/计数/引用文件；再迁移、启动、复核和验收。MySQL应另做数据库一致性逻辑备份+资产联合备份及恢复演练，不连接旧/业务库替代测试。

失败立即停止升级/重启循环，记录实际head、已创建表/列与错误，保留数据现场；不自动恢复覆盖备份、不执行降级或删表。SQLite/MySQL可能已有部分DDL，需要审查修复方案并用户确认；回退只退应用/入口并保留笔记表与迁移文件。本轮只实现并在隔离库验证，5177保持0006。


## 2026-10-23 关联文献展示决策（P3-A增量）

直接使用NoteDTO/NoteSummary.documents，不过滤当前文献、不增加数据库字段。NoteDocuments纯展示组件输出全部rows/count/full title/current badge，仅发open-document事件，不修改数组。编辑器和个人已有笔记候选复用该组件。

NotesPanel通过现有navigateReader打开关联PDF，每次保护性GET文献验证权限，使用ReaderPage已有route/草稿守卫/真实PDF就绪检查；有既存标签时采用其页码，否则第一页。导航失败与笔记操作错误分别提示，取消/账号变化使旧导航失效。

notes controller的setDocument在目标确为当前笔记关联文献时携带同一编辑器/所选note，并读取完整服务器DTO；标签只决定当前标识，绝不通过页面切换写关联。未关联目标仍用既有当前文献列表逻辑。解除/删除继续沿用P3-A-Fix已确认成功后更新缓存，不提前删除。无后端/API/数据库结构变更，不推进P3-B。

## P3-B Design（2026-10-23，当前授权）

### 内容与来源契约

复用0007的sources JSON及source_schema_version=1，不改变表结构或旧迁移。content仍为可编辑纯文本，固定呈现顺序为手写正文在前、sources数组按追加顺序在后。每个来源记录本身即显示块，稳定UUID=id=operationId，不另外向正文复制一份内容。来源块本轮只读，暂不单独编辑/删除/排序；笔记全局删除沿用明确确认。未知来源格式明确提示而不抹除。普通PATCH仅更新标题/正文，不能覆盖sources。

块字段：id、kind(pdf_excerpt/translation_excerpt)、createdAt、originalText、可选translatedText/sourceLanguage/targetLanguage、historical、服务端派生的translationProvenance(model_api/isolated_mock)、requestFingerprint，以及source={documentId,title,fileSha256,pageNumber,pageNumbers,positions,contextRevision,precision:'page'}。标题/文件指纹由服务器读取，坐标/文字范围保留客户端元数据但验证边界，当前可靠性只声明到物理页级，不声称精确跳转。后续AI回答可以新增kind，本轮不实现。

### API与事务

新增POST /api/v1/notes/captures：{operationId,noteId,version,newNoteTitle,associationMode:'link'|'keep',source:{kind,documentId,pageNumber,originalText,positions,contextRevision,translatedText?,sourceLanguage?,targetLanguage?,translationProof?,historical,confirmHistorical}}。newNoteTitle非null时原子创建笔记与首块，version=null；否则要求已有本人笔记与版本。响应{note,blockId,created,linked,replayed}，首次201，完全相同操作重放200。新增GET /notes/capture-config，不改变旧/notes/config契约。个人笔记选择可按title做标题子串分页筛选，不实现全文搜索。

验证Origin/CSRF、用户会话、有效源文献所有权与目标笔记所有权；先锁文献再笔记。已有笔记正文保存和追加共享version CAS；追加重新赋值JSON列表，禁止原地修改导致ORM漏保存。新建失败不留下空笔记。指纹绑定目标、标题、关联策略和来源内容，但不含预期version；同UUID重放先于版本判断，不重复追加，改内容复用UUID返回409。单块原文上限6000、译文上限20000、位置最多20页/512矩形，总块数及JSON体积均有上限，错误不泄露内部异常。

### 原文可靠性与翻译证明

冻结ReaderContext选区（仅PDF文字层）、文献ID、物理页码、原始文字、位置和contextRevision。延续P2乱码/字体映射保护。服务器使用同一PDF实际页提取文本做空白等价片段核验，多页逐页核验textQuote且合并后与原文等价；不修改原文、不猜测修复、不将坐标宣称为已验证精确定位。扫描件/提取无法匹配则明确拒绝并保留待保存内容。

翻译现有source不变，顶层新增translationProof={version,issuedAt,signature,provenance}；使用域分离会话HMAC绑定用户、文献/文件版本、原文/译文、物理页码、方向、contextRevision、时间和来源类型，保存时验签、权限及有效期，不再次调用模型、不读取模型密钥。测试环境始终标isolated_mock，不能冒充model_api。旧无回执结果可显示但不能保存为可信译文。

点击保存当前译文前，必须同时比较实际ReaderContext与结果（文献、选区、页码/位置、方向）；不匹配则只能作为明确历史结果保存并再次确认，使用结果自身来源而不是当前标签。对话框打开时冻结意图，焦点引起选区折叠不能篡改该意图；真实切换文献/账号关闭目标对话框，旧请求不得覆盖新目标。

### 关联语义与编辑协调

现有笔记未关联源文献时，用户必须明确选择“同时关联来源文献”或“仅保存来源，不新增关联”，不静默添加；新建笔记的关联选项也明确展示。解除关联只影响M:N列表，已保存来源块不删除，卡片提示其源文献当前未关联。A摘录在B打开仍显示A快照，切换标签或编辑正文均不改来源。永久删除文献仍保留本人笔记内来源快照，不自动重建关联。

目标选择提供新建、当前推荐和个人已有笔记分页/标题搜索，可更换目标。打开前flush现有编辑，失败阻止插入以保护草稿；提交前读取最新目标版本，冲突不覆盖，重试保留operationId和内容快照。保存中禁重复操作，网络失败保留原文/译文和目标，成功明确提示并刷新笔记及完整关联集合。来源卡用安全文本呈现，翻译/笔记独立开关及窄屏PDF布局保持。

### 兼容、备份和失败处置

旧笔记sources=[]直接兼容，无回填、无schema迁移；0007文件保持不变，SQLite与MySQL均用现有JSON整列CAS赋值，真实MySQL仍待独立验证。5177保持0006/原进程，不用其启动器。只在独立临时SQLite和隔离浏览器验证，再正常停止5180，备份整个.cache/notes-preview到项目外唯一时间戳目录，核对相对路径/数量/大小/SHA256、副本SQLite只读integrity/FK/计数及PDF引用，再启动原预览命令。启动前核对head=0007、清理候选为空、C/D空间至少10GB，不覆盖已有备份；失败保留现场，不自动还原或重试。

5180若使用翻译Mock，必须在独立测试配置显式启用，页面及来源块醒目标“隔离Mock，非真实模型译文”，不加载真实模型密钥。自动化测试分别记录Mock/SQLite/浏览器；本轮不新增真实模型调用、真实MySQL验证或5177部署结论。

## P3-C1 Design（2026-10-25，当前授权）

### 搜索契约与安全边界

新增认证只读接口`GET /api/v1/notes/search?q=&page=&pageSize=`，静态路由必须注册在`/{id}`之前。`q`去除首尾空白后最长100字符；空关键词返回空结果，分页默认20、上限50。拒绝未知或重复查询参数。搜索仅从`Note.owner_id == session.user_id`的笔记本体开始，不连接`note_documents`做候选集合，保证同一笔记即使关联多篇文献也只返回一次；DTO继续通过既有owner过滤生成完整有效关联文献列表。

匹配字段限定为title、content及sources数组内受支持块的originalText/translatedText。查询按Unicode字面量子串处理，英文大小写不敏感；不把`%`、`_`、正则或SQL片段当通配符/表达式。为兼容SQLite JSON和MySQL JSON编码差异且避免迁移，本阶段在应用层对本人Note行做受限只读匹配，不依赖数据库JSON方言、FTS、向量或模型。每条笔记最多返回6个命中片段，每段最多约160字符并携带服务器计算的实际高亮起止位置、field/label以及可用的来源块ID/文献ID/页码；响应不返回完整正文或sources。结果按updated_at倒序及id稳定排序、分页并报告唯一笔记总数。

该方案对个人中小规模笔记可靠且跨当前SQLite/MySQL ORM模型；账号笔记数量或单笔记内容显著增长后应另立性能变更评估数据库全文索引。P3-C1不新增表、索引、迁移或依赖，也不搜索未保存的sessionStorage草稿、整篇PDF、关联文献标题和未知来源格式。

### 前端状态与草稿保护

`NotesApi`增加search，控制器维护与当前文献列表分离的query/appliedQuery/items/loading/error/page状态及独立请求序号。输入稳定350ms后请求；新输入、清空、账号切换和dispose取消定时器并使旧响应失效。清空查询只恢复已缓存的正常当前文献列表，不额外写笔记。搜索错误、空结果、加载中及分页均在搜索区域独立呈现，不覆盖CRUD错误。

搜索结果展示笔记标题、命中位置和纯文本片段；高亮用服务端start/end切片和Vue文本节点/`mark`，不用`v-html`。点击结果复用现有`choose`，它先flush当前编辑器；保存失败或冲突时保持草稿并阻止切换。搜索输入、请求、关闭面板和普通文献标签切换本身不得调用PATCH或改写来源、关联、页码；打开结果后继续显示完整NoteDTO关联和来源块。

### 验证与预览边界

后端临时SQLite覆盖中英文/大小写/正文/原文/译文/特殊字符/多关系去重/跨用户隔离/分页与无写入。前端单测覆盖350ms防抖、旧响应失效、清空恢复、失败重试、命中高亮和草稿守卫；临时SQLite浏览器覆盖真实HTTP搜索与原有笔记/来源交互。完成代码和测试后仅用既有notes-preview启动器安全重载5180，保留10GB自动停止、Mock翻译和现有preview.db/PDF/备份；不迁移5177、不进入P3-C2。

## P3-C2-A Design（2026-10-25，当前授权）

### 可靠来源与公共导航

来源卡只对可识别source_schema_version=1块提供“查看原文”。定位对象使用块内不可变的source.documentId、source.fileSha256和source.pageNumber；标题只展示，note_documents仅展示关联状态，均不作为定位依据。缺少非空文献ID、64位十六进制哈希或正物理页码时保留来源显示但禁用导航，并明确“无法可靠定位来源”。普通正文没有来源按钮。

受保护DocumentDTO的attachment增加只读sha256，用于公共navigateReader在调用host前核对当前账号权限和文件版本；若服务端文献不存在/越权、哈希缺失或不一致，返回稳定错误且不切标签。已知pageCount可提前拒绝越界；ReaderPage加载真实PDF后仍以numPages复核，防止未知/陈旧页数跳到错误页。该字段为现有DocumentFile摘要的只读增量响应，不增加数据库字段或迁移，所有DocumentDTO消费者只接受兼容性可选展示，不持久化或修改摘要。

### 标签、加载竞态与编辑保护

NotesPanel复用createNotesController.flush和既有CAS/会话草稿：点击来源先保存当前编辑；失败或冲突则保留输入并阻止导航。成功导航复用navigateReader与ReaderPage已注册host：已开文献切换现有标签，未开文献走原路由/openReaderTab，等待真实PDF就绪后调用jump(pageNumber)。本阶段不传position、不创建页内高亮。

每次来源点击冻结noteId/source block/账号，使用AbortController和单调epoch。新点击取消旧请求；旧权限查询、旧PDF加载或旧返回不得显示成功、改页或重新选择旧笔记。跨文献成功后调用既有setDocument并按noteId重新GET本人笔记，使未关联来源文献也能继续显示原笔记；这不调用link/unlink/PATCH来源，不改变关联集合、source快照或搜索查询。面板开关由ReaderPage现有标签状态保存。

### 异常与验证边界

统一将缺失元数据、DOCUMENT_NOT_FOUND、SOURCE_VERSION_MISMATCH、INVALID_PAGE、DOCUMENT_UNAVAILABLE和取消以可理解状态呈现；取消的旧操作保持静默，当前操作明确失败。不得以相似标题、文件名、当前标签、正文匹配或关联列表代替来源ID/哈希。异常PDF可展示已存摘录，但只有通过权限/哈希/实际页数检查才报告定位成功。

临时SQLite真实HTTP浏览器覆盖同文献、跨文献、已开/未开标签、多来源、搜索结果、未保存草稿、未关联来源、哈希/页码/权限错误和快速点击；回归P3-A/B/C1。5180加载前按既有流程核对/备份数据与PDF，保留10GB保护和Mock标识。P3-C2-B页内坐标/文字高亮、跨行重匹配及OCR不在本阶段。

## P3-C2-B1 Design（2026-10-26，当前授权）

### 可证明的精确位置

P3-B已经保存每页`SelectionPosition`：物理`pageNumber`、未旋转PDF/CropBox坐标归一化`rects`、该页`textQuote`和可选PDF.js `textRanges(item,start,end)`。当前5180两个来源块均有有效文件摘要、单页position、多个rect和textRanges，但服务端`precision:'page'`只证明原文存在于该页，不证明客户端坐标。因此B1不直接信任矩形，也不修改旧precision或来源JSON。

来源卡只把与`source.pageNumber`相同、矩形边界合法且textRanges结构完整的position传给公共导航。身份/哈希/真实页数仍由C2-A先验证。目标`PdfPage`必须等待当前文件、页码、缩放和PDF内置旋转对应的TextLayer完成，用保存的item及UTF-16半开区间从当前span逐段重建文字，并严格比较换行标准化后的`textQuote`；不折叠空格、不删除连字符、不搜索相似文本。范围越界、顺序异常、文本不等或无可见DOM矩形均降级为页码成功。

### 临时层、时序和生命周期

`PdfPage`从当前DOM Range的`getClientRects()`计算显示坐标，故当前缩放、CropBox、UserUnit和PDF内置Rotate由同一TextLayer viewport处理；高亮层位于文字下、批注下，`pointer-events:none`，不改变原生Selection、PDF、notes.sources或批注。多行产生多个矩形。ReaderPage收到精确结果后只居中滚动一次；之后用户滚动不再被拉回。页面因缩放/虚拟化重新渲染时，同一已验证请求可从文字范围重建高亮，但不再次抢滚动。

每次来源请求先清除旧高亮并增加epoch；AbortSignal、文献generation和高亮token共同拒绝迟到结果。切换/关闭文献、账号变化、load开始或组件卸载清理。缺少可靠position时直接页码跳转并返回`precision:'page'`；精确完成返回`precision:'exact'`。TextLayer在有界等待内未完成也只降级，不影响C2-A页跳转。

### B1边界与验证

B1只高亮`source.pageNumber`对应的单页position；跨物理页摘录的后续页面联动、用户可控页面旋转、旧块无textRanges、PDF.js升级造成item边界变化、模糊文字重匹配及OCR均不宣称支持。当前阅读器没有用户页面旋转状态；PDF内置旋转由viewport/TextLayer覆盖。临时SQLite/PDF.js浏览器使用实际可复制合成PDF覆盖单行、多行、跨文献、首次/已有标签、搜索、草稿、快速点击、无范围和哈希变化，并回归笔记/批注。5180加载前继续完整备份、10GB保护和Mock翻译；5177不动。


## P3-D1 增量边界（2026-10-26）

复用既有notes.sources JSON及0007结构，增加判别类型ai_answer，基础正文/旧PDF和译文块不改，不新增迁移。默认回答服务不可用；通过依赖注入替换服务端权威读取适配器。输入仅回答ID/修订及历史/无引用确认，内容与引用由服务端取得并再次核对owner、文献/PDF摘要、物理页和原文。回答问题/正文与可信PDF引用分开呈现；无引用必须确认“未核实”，校验失败不允许降级。

沿用captures事务、operationId、note.version CAS、现有目标选择和flush/草稿保护；同笔记同回答修订重复保存返回既有块，不隐式重关联。AI引用只复用可靠页跳转，不伪造textRanges。5180专用Mock工具不属于正式问答面板；只有显式隔离脚本启用，并验证测试路径/配置；合成PDF及固定回答明确标识模拟。普通应用不注册测试路由。字段与服务端解析协议仍待06负责人确认，D2不在本次范围。
