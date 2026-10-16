# 统一 API 与跨模块契约 v1（Change 01、02 A1/A2/B1 已实现，后续规划）

## P3-B1 实现约束（2026-10-15）

生产者：backend/app/annotations.py；消费者：frontend/src/reader/annotations.ts、PdfAnnotations.vue、AnnotationList.vue。保留后文完整14类目标契约，实际B1只开放六类，不开放资产/导出。

- geometry=text的positions必须与position完全相同，非空逐页rects/textQuote且selectedText非空；起始pageNumber必须一致，服务端用原PDF真实页数验证全部子页。四种文本标记只用text；comment用text或anchor；freeText只用box（rotation=0），坐标始终是未旋转CropBox左上归一化值，不能越界或含NaN/Infinity。
- `color`必为#RRGGBB（默认#F5D547），透明度独立；style只接受stroke/fill、opacity(0,1]、lineWidth 0.25–20pt、fontSize 6–144pt，默认1/1/14。PATCH changes允许color/content/style/geometry/zIndex，style子字段合并，type/id/文本锚点不可修改，非文本几何可在原页移动/改框。comment/freeText正文非空，纯文本由Vue按文本输出，不执行HTML；单字段最多20k字符、单对象序列化最多1MiB、单篇最多10k活动对象，不截断。
- POST默认生成ID，也接受客户端ID；未知字段、B2类型、assetId非null、非法页码/几何/属性返回422。起始集合revision为0；任何写入以commandId+baseRevision提交，PATCH/DELETE另携带对象version。陈旧集合/对象、同commandId不同请求、无效恢复返回409；同用户错文献/他人文献、对象或收据404，缺会话401，Origin/CSRF无效403。
- DELETE返回annotation=null并将对象保留为墓碑、version+1。restore提交原DTO快照，要求同owner/document/ID、原快照字段及`快照.version+1 == 墓碑.version`；恢复不覆盖活动对象，成功后对象再version+1。创建、编辑、删除、恢复均原子递增annotationRevision并保存完整MutationResult收据；重复同请求不改变版本。收据24小时有效，GET过期返回404 COMMAND_NOT_FOUND，旧baseRevision不会被盲重放。
- 客户端每文献独立1秒自动保存串行队列，draft/sending/confirmed/failed/conflict分开；请求8秒超时。任何已准备命令先按ID核对收据，结果未知的重试保留原commandId/请求体。失败停止依赖写入、保留sessionStorage草稿并可重试/导出；409不自动改用新版revision覆盖，显式载入服务端时备份草稿、清撤销历史，备份有导出入口。无自动合并/导入JSON功能；可根据保留草稿人工核对重建需要的修改。
- 已保存undo/redo为真实补偿命令，恢复原ID；最多100条，不跨刷新。切文献、关闭活动标签、回库先flush，失败保留当前页，也可显式保留原待确认命令到本地后返回库；编辑窗未确认则阻止离开，浏览器刷新/关闭有beforeunload提示，已入队草稿可在刷新后恢复。输入/可编辑元素使用自身撤销；进度队列及版本独立。退出清理私有草稿，在途回执不会在退出后重新写入本地草稿。

实现和精度/测试边界见[B1记录](../development/p3-b1.md)。下文“仍为规划”“仅A2”等历史描述由本节覆盖，仅适用于尚未实现的B2/C及03–06部分。

本文件为统一API契约。Change 01 及02 A1/A2已通过用户功能/UI验收；02 B1已实现六类文本批注接口，资产/导出及03–06接口仍为规划。API 前缀 `/api/v1`；JSON 使用 camelCase、UTF-8。所有 ID 为不透明 string（实际 UUID），时间为 UTC ISO 8601，展示使用本地时区；物理 PDF 页码从 1 开始，不等同印刷页标签。

## P3-A1已实现接入（2026-10-15）

reader路由及文献库阅读已改PDF.js 6.4.299，复用GET文献详情/受保护content/Range及原件下载，无新后端业务接口。A1交互补充改为首个真实页面完整渲染后调用原PUT progress {}一次，只由服务器更新lastReadAt；下载/题录/渲染失败不记，写失败提示重试。实际页码/缩放/模式持久化已由P3-A2完成。下文01浏览器预览说明为历史实现，02对象/资产/导出仍为后续目标；扩展ProgressDTO已实现，不表示本轮交付。见[P3-A1](../development/p3-a1.md)。

## 通用约定

### P2-B 当前实现（2026-10-14）

Change 01表中的分类、检索、最近阅读、回收站已实现。列表允许title/year/createdAt/lastReadAt排序；q搜索标题、作者、摘要、关键词、DOI及期刊，参数化LIKE并转义通配符；tagIds逗号分隔全部匹配，年份1–9999且区间有序。重复或未知查询参数422，分类归属错误404。文件夹/标签名称NFKC、trim、casefold后用户内唯一，1–100可见字符；标签color可空或#RRGGBB。GET /folders和/tags返回DTO数组。

PATCH增加folderId（null未分类）和tagIds（null/[]解除全部关联），省略保持；题录和分类通过同一version CAS原子保存。分类删除同时解除回收站文献关联并递增受影响文献版本，不删除PDF。

01实际提供GET/PUT /documents/{id}/progress的已打开子集：PUT `{}`更新服务器lastReadAt和progress.version，重复打开更新同一记录；GET内容/列表/下载不写历史。历史01曾对非空pageNumber/zoom返回503；A2已兼容扩展，当前规则见下文。可选version校验冲突409。GET /reading-history支持与文献列表相同过滤，始终按lastReadAt倒序（sort/order仅校验），返回既有document/progress分页包络。该段为01历史子集，A2已实现真实页码/缩放。

新增兼容接口POST /cleanup-jobs/{jobId}/retry（Origin/CSRF/owner检查）：完成204，否则202作业DTO；GET作业也返回attempts/updatedAt。DocumentDTO增加nullable cleanupJob `{jobId,status,errorCode}`，仅本人回收站显示，无内部存储路径。永久清理开始后不可恢复；pending/failed或运行租约过期可重试，工作行锁与尝试编号阻止并发重复领取；失败持久化并返回202，不能当删除成功。完成后保留审计作业且清空storageKey，释放原PDF的用户内重复约束。具体状态及验收见[P2-B记录](../development/p2-b.md)。上述添加仅属于01，不改变02–06待实现业务。

### P2-A 历史实现范围（2026-10-14，分类限制已由P2-B解除）

P2-A已实现POST/GET /documents、GET/PATCH /documents/{id}、GET /documents/{id}/content和受认证GET /library/config。后者返回`{maxUploadBytes:number}`，默认52428800；前端从真实配置读取上限。列表本轮只支持page/pageSize和title/year/createdAt的sort/order；组合过滤参数返回503 FILTERS_NOT_READY，不忽略或模拟筛选。lastReadAt排序、分类、progress/history、trash/cleanup仍为P2-B规划。

PATCH本轮只允许title/authors/abstract/keywords/year/journal/doi/version；非法身份/分类字段返回422，分类关联在P2-B开启。标题1–500字符，作者最多100位且每位1–200字符，关键词最多100项且每项1–100字符，摘要最多50000字符，年份1–9999整数或null，期刊最多500字符，DOI最多255字符。省略保持，null清空可选值，authors/keywords清空后返回[]；title不能null或空白。DTO的folderId=null、tags=[]、lastReadAt=null、pageCount=null为该阶段的真实未设置值。

上传只支持一个file字段，不依赖浏览器MIME判断真实性，以PDF签名及结构校验为准；损坏/加密/零页PDF返回415，用户先解密。提交folderId返回503 CLASSIFICATION_NOT_READY，其余未知multipart字段返回422。逐文件限额严格执行MAX_UPLOAD_BYTES，请求流同时限制为该值+64KiB multipart封装开销，避免解析前无限落临时盘。单Range支持闭区间、开放尾端和后缀范围；非法或多Range返回416标准错误包络并携带Content-Range。download=true返回UTF-8原文件名attachment。

DocumentUploadedV1仅定义于backend/app/events.py，未启用派发/队列/提取。/reader/:documentId保留原ID跳转至库详情，明确在线阅读器待实现。验收证据见docs/development/p2-a.md；真实SQLite/本地HTTP通过不代表MySQL部署已验收。

成功返回资源对象；列表 `{items: T[], page: number, pageSize: number, total: number}`；写入新资源 201，异步作业 202，普通查询/更新 200，无响应体删除/退出 204。分页默认 page=1、pageSize=20，允许 1–100；排序字段白名单，稳定增加 id 作为第二排序键。

错误统一 `{error: {code: string, message: string, details?: object}, requestId: string}`。400 非法业务输入，401 会话失效，403 CSRF 不通过，404 不存在/非本人/不可访问资源，409 重复或版本冲突，413 文件超限，415 不支持文件，422 字段/页码校验失败，429 调用频率限制，502/504 外部服务失败/超时，503 功能或依赖未就绪。FastAPI 默认校验异常也转换为此包络，不暴露路径/堆栈/供应商秘密。

认证使用 Cookie 会话（建议方案见 architecture）；除注册登录外全部业务接口需当前用户。JSON 写入与 multipart 上传都携带 `X-CSRF-Token`；Origin 校验适用于登录注册与其他写入。客户端不得传 ownerId 来决定身份。每个嵌套文献、文件夹、标签、批注、chunkId、sourceId 都校验归属与关联，不只校验最外层文献。

## Change 01：身份、文献库

| 方法/路径 | 输入 | 输出/关键规则 |
| --- | --- | --- |
| POST /auth/register | `{email,password,displayName}` | 201 UserDTO；规范化邮箱唯一；不自动登录 |
| POST /auth/login | `{email,password}` | 200 `{user,csrfToken}` + Set-Cookie；错误统一无效凭证 |
| GET /auth/session | 无 | `{user,csrfToken}`；401 时前端清理阅读状态 |
| POST /auth/logout | 无 | 204；撤销当前会话并清 Cookie |
| GET /users/me | 无 | UserDTO，不返回 hash/token |
| PATCH /users/me | `{displayName}` | UserDTO；首版不变更邮箱/密码 |
| POST /documents | multipart `file`、可选 `folderId` | 201 DocumentDTO；合法 PDF；重复 409 DUPLICATE_DOCUMENT |
| GET /documents | `q,folderId,tagIds,yearFrom,yearTo,sort,order,page,pageSize` | 本人未删除文献分页；q 搜索标题/作者/摘要/关键词/DOI/期刊；tagIds 逗号分隔，采用全部匹配 |
| GET /documents/{id} | 无 | DocumentDTO |
| PATCH /documents/{id} | 元数据可写字段、folderId、tagIds、`version` | 更新 DTO；版本不一致 409；null 清空，省略保持 |
| GET /documents/{id}/content | Range、可选 `download=true` | PDF 二进制；206/416；下载为 attachment，否则 inline |
| DELETE /documents/{id} | 无 | 204；软删除，重复删除已在本人回收站时幂等 |
| GET /trash/documents | 分页 | 本人已删除文献 DTO |
| POST /trash/documents/{id}/restore | 无 | 200 DTO；恢复关联，无重复新建 |
| DELETE /trash/documents/{id} | 无 | 204 永久删除完成；清理中 202 `{jobId,status}`，可查 GET /cleanup-jobs/{jobId} |
| GET /cleanup-jobs/{jobId} | 无 | `{jobId,documentId,status,errorCode,attempts,updatedAt}`；仅本人，status=pending/running/completed/failed |
| POST /cleanup-jobs/{jobId}/retry | 无 | 完成204，否则202作业DTO；仅本人，已开始永久清理不可恢复 |
| GET、POST /folders | POST `{name}` | 列表/201 FolderDTO；同用户同名冲突 409 |
| PATCH、DELETE /folders/{id} | PATCH `{name}` | DTO/204；删除文献归未分类，不删除文献 |
| GET、POST /tags | POST `{name,color?}` | 列表/201 TagDTO；同用户同名冲突 409 |
| PATCH、DELETE /tags/{id} | PATCH `{name,color?}` | DTO/204；删除解除关联，不删除文献 |
| GET /reading-history | 分页 | 本人最近阅读 `{document:DocumentDTO,progress:ProgressDTO}[]` 的分页包络 |

sort 允许 title、year、createdAt、lastReadAt，order=asc/desc；空年份/最近阅读排在末尾。筛选支持年份区间/文件夹/标签，文献检索限定个人库。01 为浏览器预览使用进度接口的“记录已打开”子集：pageNumber/zoom 可空、lastReadAt 由服务器写入；02 再扩展实际页数/缩放。当前响应没有 openedAt 字段。

上传 DTO：title 初值由文件名（去扩展名）产生，authors=[]，未知元数据=null/[]，parseStatus=not_requested。重复错误 details 仅可包含本人 existingDocumentId、inTrash；若在回收站提示恢复，不悄悄重建。阶段 01 不调用任何解析或 AI。

## Change 02：阅读、对象与导出（目标契约，尚未实现）

2026-10-15以[02设计](../../openspec/changes/02-pdf-reader/design.md)为本模块细节来源。01的当前实现/历史段保留；以下不表示API已提供。前缀仍为/api/v1，复用会话、Origin/CSRF、错误包络与owner/有效文献过滤。

| 方法/路径 | 目标输入/输出 | 一致性规则 |
| --- | --- | --- |
| GET /documents/{id}/annotations | `{items:AnnotationDTO[],annotationRevision}`；可选pageNumber过滤包括多页锚点涉及该页的对象 | 本篇全体含14类对象；分页若后续加入须快照一致，不静默漏项 |
| POST /documents/{id}/annotations | `{commandId,baseRevision,annotation:{id?,type,pageNumber,position,geometry,style,assetId?,selectedText?,content?,color?,zIndex,schemaVersion}}` →201 MutationResult | id可由客户端生成以支持恢复/幂等；服务端校验唯一及归属 |
| PATCH /documents/{id}/annotations/{annotationId} | `{commandId,baseRevision,version,changes}` →200 MutationResult | type不可变；文本锚点重选创建新对象；box/path几何可编辑 |
| DELETE /documents/{id}/annotations/{annotationId} | JSON `{commandId,baseRevision,version}` →200 MutationResult | 删除也CAS且保留幂等收据，不再沿用旧规划无版本204 |
| POST /documents/{id}/annotation-commands | `{commandId,baseRevision,operation:'restore',annotation:已删除对象快照}` →200 MutationResult | 仅恢复本人同篇原ID，不覆盖其他现存ID；资产必须仍有效 |
| GET /documents/{id}/annotation-commands/{commandId} | 已确认MutationResult或404 COMMAND_NOT_FOUND | 超时核对，命令同事务入收据，保留24小时；过期须重读集合 |
| POST /documents/{id}/reader-assets | multipart PNG/JPEG；→201 `{assetId,mimeType,width,height,sizeBytes}` | 同源防伪，真实解码/容量校验；不接受远程URL或SVG |
| GET /documents/{id}/reader-assets/{assetId}/content | 二进制 | owner/document双重关联，不公开存储键 |
| DELETE /documents/{id}/reader-assets/{assetId} | 未引用临时资产删除，204 | 已被对象/导出引用409；对象删除的回收由生命周期处理 |
| GET /documents/{id}/progress | 扩展ProgressDTO | 旧null字段按continuous/fit-width读取 |
| PUT /documents/{id}/progress | `{pageNumber?,zoom?,viewMode?,zoomMode?,version?,recordOpen?}` | 新状态写必须version；未读0、旧版本409；保留旧PUT {}仅记打开 |
| GET /documents/{id}/content?download=true | 原始PDF | 复用01，不改原字节，不记阅读 |
| 带批注导出协议（C1冻结路径） | 受保护POST接受`expectedAnnotationRevision`，下载快照PDF；若异步提供状态/取消/下载 | 不能提前视为可调用API；C1 ADR决定同步/作业协议，所有阶段复验权限 |

MutationResult=`{commandId,annotationRevision,annotation:AnnotationDTO|null}`；读取集合revision、对象version和写入baseRevision共同防并发丢失。相同commandId/相同请求返回原结果，内容不同409；事务失败不得留下部分对象/集合版本。客户端同文献串行写、补偿undo/redo也经这些接口，不仅改本地数组。草稿/在途/确认/失败分开；409保留本地并显式选择恢复/重放。

服务端复用已锁pypdf校验真实页数，客户端pageCount不能决定权限/页范围。zoom对外倍率0.5–5，数据库继续字符串。新字段省略保持，新增设置显式null拒绝422；旧pageNumber/zoom为null的打开请求兼容。recordOpen为严格boolean，默认true兼容旧打开请求；A2首目标页成功后写true，后续自动保存写false（不更新最近打开时间）；false及任何非空状态写必须version。成功首目标页渲染后写阅读，1秒防抖/持续最多5秒一次；PUT {}不清页/缩放/模式。题录version、progress.version、annotation.version、annotationRevision、contextRevision互相独立。

对象/资产限额、坐标、幂等/收据保留、清理和导出资源预算见02设计。软删保留但普通访问404、恢复同ID，永久清理接原cleanup_jobs且失败可重试。导出仅已保存一致快照，不混合修订；“第三方可见”与“第三方可编辑”分开验收，不承诺全类型原生可编辑。

上表中 B1 的 annotations CRUD、restore 和收据查询现已实现；reader-assets 和导出仍不可调用。B1输入只接受 highlight/underline/squiggly/strikeout/comment/freeText，schemaVersion=1、assetId=null。具体校验及错误见末尾B1实现说明。

## Change 03–06：预期接口，全部待实现

| 模块/方法/路径 | 输入 | 输出/约束 |
| --- | --- | --- |
| 03 POST /documents/{id}/translations | `{context:ReaderContext,sourceLanguage:'zh'|'en',targetLanguage:'zh'|'en',text}` | `{translationId,documentId,pageNumber,sourceText,translatedText,sourceLanguage,targetLanguage,contextRevision}`；空文本/同语言422 |
| 04 POST /notes | NoteDraft | 201 NoteDTO；关联权限及来源校验 |
| 04 GET /notes | `q,documentId?,page,pageSize` | 本人笔记分页；按内容/标题搜索 |
| 04 GET、PATCH、DELETE /notes/{noteId} | PATCH `{title?,content?,version}` | DTO/204；版本冲突409 |
| 05 POST /documents/{id}/extractions | 无；用户显式重试 | 202 `{jobId,documentId,status}`；同文件版本运行中返回原作业 |
| 05 GET /documents/{id}/extractions/latest | 无 | ExtractionResult 或 404；未完成返回明确状态 |
| 05 GET /extraction-jobs/{jobId} | 无 | 作业 DTO，归属验证；错误可重试 |
| 05 GET /documents/{id}/text | `extractionVersion,pageNumber?` | `{documentId,extractionVersion,pages:ExtractedPage[]}`；无该版本404 |
| 06 POST /documents/{id}/qa | `{mode:'summary'|'analysis'|'question',question?,context:ReaderContext}` | AnswerDTO；question 模式必须非空；context.documentId 必须等于路径 |

05 人工校正通过 01 的 PATCH /documents/{id}，提交 version 和明确选中的候选字段；不另造不兼容题录写接口。06 初版返回完整响应，暂不规定 SSE；未来加流式接口需单独补契约。03/06 来源结果只供当前用户使用，04 保存 NoteDraft 时验证 sourceId 的所属文献/用户，禁止伪关联。

## 核心 DTO（TypeScript 文档示例）

UserDTO、DocumentDTO、分类和完整阅读进度已有实现；ReaderContext/SelectionPosition/NoteDraft/Citation源码见frontend/src/reader/context.ts（后两者仅类型），ProgressDTO见reader/progress.ts。六类AnnotationDTO源码见reader/annotations.ts，其他对象及03–06业务DTO仍为目标契约。ProgressDTO.zoom对外为number/null，ORM为nullable VARCHAR(20)，合法倍率0.5–5，不重复创建reading_progress。

```typescript
interface UserDTO { id: string; email: string; displayName: string; createdAt: string }
interface FolderDTO { id: string; name: string }
interface TagDTO { id: string; name: string; color: string | null }
type ParseStatus = 'not_requested' | 'queued' | 'processing' | 'completed' | 'failed';
interface DocumentDTO {
  id: string; title: string; authors: string[]; abstract: string | null;
  keywords: string[]; year: number | null; journal: string | null; doi: string | null;
  folderId: string | null; tags: TagDTO[];
  attachment: { originalName: string; sizeBytes: number; mimeType: 'application/pdf' };
  parseStatus: ParseStatus; extractionVersion: string | null;
  pageCount: number | null; version: number;
  createdAt: string; updatedAt: string; lastReadAt: string | null; deletedAt: string | null;
    cleanupJob: { jobId: string; status: 'pending'|'running'|'completed'|'failed'; errorCode: string|null } | null;
}
interface NormalizedRect { x: number; y: number; width: number; height: number }
interface SelectionPosition {
  pageNumber: number; rects: NormalizedRect[]; textQuote: string;
}
interface ReaderContext {
  documentId: string; pageNumber: number; selectedText: string;
  selectionPosition: SelectionPosition[] | null;
  annotationId: string | null; contextRevision: number;
}
type ReaderViewMode = 'continuous'|'single'|'spread';
type ReaderZoomMode = 'custom'|'fit-width'|'fit-height';
type AnnotationType = 'highlight'|'underline'|'squiggly'|'strikeout'|'comment'
  |'freeText'|'ink'|'marker'|'rectangle'|'circle'|'ellipse'|'signature'|'watermark'|'image';
// 全部坐标相对未旋转CropBox；笔宽/字号为PDF point。B1六类已有源码，其他类型待B2。
type AnnotationGeometry =
  | { kind:'text'; positions:SelectionPosition[] }
  | { kind:'box'; pageNumber:number; rect:NormalizedRect; rotation:number }
  | { kind:'path'; pageNumber:number; points:{x:number;y:number}[] }
  | { kind:'anchor'; pageNumber:number; x:number; y:number };
interface AnnotationDTO {
  id:string; documentId:string; type:AnnotationType; schemaVersion:1;
  pageNumber:number; position:SelectionPosition[]|null; geometry:AnnotationGeometry;
  selectedText:string|null; content:string|null; color:string|null;
  style:{stroke?:string;fill?:string|null;opacity?:number;lineWidth?:number;fontSize?:number};
  assetId:string|null; zIndex:number; version:number; createdAt:string; updatedAt:string;
}
interface ProgressDTO {
  documentId:string; pageNumber:number|null; zoom:number|null;
  viewMode:ReaderViewMode; zoomMode:ReaderZoomMode;
  lastReadAt:string|null; version:number;
}
interface Citation {
  documentId: string; extractionVersion: string; chunkId: string;
  pageNumber: number; quote: string;
}
interface NoteDraft {
  documentId: string; pageNumber: number | null; annotationId: string | null;
  title: string; content: string;
  sourceType: 'manual'|'selection'|'translation'|'ai'; sourceId: string | null;
  originalText: string | null; translatedText: string | null; citations: Citation[];
}
interface NoteDTO extends NoteDraft {
  id: string; version: number; createdAt: string; updatedAt: string;
}
interface ExtractedPage { pageNumber: number; text: string }
interface TextChunk {
  chunkId: string; documentId: string; extractionVersion: string;
  pageNumber: number; startOffset: number; endOffset: number; text: string;
}
interface ExtractionResult {
  documentId: string; extractionVersion: string; fileHash: string;
  status: 'queued'|'processing'|'completed'|'failed';
  metadata: { title: string | null; authors: string[]; abstract: string | null;
    keywords: string[]; year: number | null; journal: string | null; doi: string | null };
  fieldSources: Record<string, { pageNumber: number | null; confidence: number | null }>;
  pages: ExtractedPage[]; chunks: TextChunk[];
  warnings: string[]; errorCode: string | null;
}
interface AnswerDTO {
  answerId: string; documentId: string; contextRevision: number;
  extractionVersion: string;
  status: 'answered'|'insufficient_evidence'; answer: string;
  citations: Citation[];
}
```

NormalizedRect 相对于 PDF 未旋转可见CropBox，以左上角为原点，x/y/width/height 位于 0–1，边界不能越出页面；缩放、设备像素比和旋转在 PDF.js 适配层转换，不持久化 CSS 像素。多页选区按页数组，ReaderContext.pageNumber 为选区起始页，未选中文本时 selectedText=''、selectionPosition=null。四种文本标记必须有非空rects；comment可页级或选区级。marker为半透明自由轨迹，与真实文本highlight区别。独立书签不属于02本次范围。手工及未形成批注的选段笔记 sourceId 可 null，选段须有 originalText/有效页码；翻译与AI笔记 sourceId 必须为本人同文献的 translationId/answerId。

TextChunk 只跨一个物理页，offset 按提取页文本的 Unicode code point 计数，半开区间 `[startOffset,endOffset)`，不依赖 JS UTF-16 索引；跨页内容用多个 chunk 和多条引用表达。引用 pageNumber/quote 必须能在对应版本页文本核对，服务端校验证据，客户端不信任模型随意编造的页码。

## 上传扩展点与接入事件

内部 `DocumentUploadedV1={eventId,documentId,ownerId,fileHash,storageKey,occurredAt}` 仅在存储与 DB 提交成功后可发出。storageKey/ownerId 不进入公开 DocumentDTO。01 定义契约且 parseStatus=not_requested；05 启用后可靠入队 queued，并按 `(documentId,fileHash,eventId)` 幂等消费，读取文件前再次校验文献有效。完成提取原子发布版本，禁止部分 pages/chunks 被 06 读取。

`ExtractionReadyV1={documentId,ownerId,extractionVersion,fileHash}` 通知 06 建索引；索引就绪前回答 503 INDEX_NOT_READY，不编造答案。文献软删除时取消/屏蔽在途任务；永久删除清理正文、chunks、向量与来源记录。ReaderEvents 见 UI 文档，context-change 是最新值快照，contextRevision 在切换文献/页码/选区时递增。

## P3-A2 公共阅读上下文（已实现）

生产者为ReaderPage真实PDF文本选区、页码/文献生命周期；消费者为后续03选区翻译、04笔记来源、06上下文，05仅复用documentId/物理页码。`subscribeReaderContext(callback)`返回取消订阅函数；事件为context-change、selection-change、document-change、context-cleared。也提供`window`上的`litera:reader:<事件名>` CustomEvent，detail为不可变快照，清理事件detail=null。`readerContext`为只读快照ref；消费者必须核对documentId+contextRevision，不能把上下文当权限凭证。跨页选区pageNumber取起始页、每页rects/textQuote；取消选区后selectedText=''且selectionPosition=null。

进度失败保留本地草稿并阻止静默路由离开；若PDF本身加载失败则保留草稿并允许回库，重放设置必须等待真实目标帧成功；sessionStorage只存用户/文献隔离的页码/设置，不存PDF或选中文本，退出清理。409读新版后明确选择载入服务端/保存本地；网络超时若结果未知，重试旧版本会409，不能自动用新版本覆盖。请求保护和后端owner校验与01一致。

### P3-B1选区精度兼容补充（2026-10-16）

SelectionPosition的每页对象新增可选`textRanges: [{item,start,end}]`，item为PDF.js TextLayer文本item索引，start/end为该item中UTF-16字符偏移，左闭右开，严格整数、item/start>=0且end>start，最多2000段。原rect可选`baseline`为字体升部/完整行框比例（有限0–1）；原x/y/width/height规则不变。四类文本标记共用这些字段，geometry.positions与position仍须完全一致。缺省时不序列化新字段、不强制补null，旧对象/命令墓碑与恢复仍兼容，非法范围422。字段直接存原JSON，不新增表/列/迁移；端点精度来自当前原生Range，不从摘要反推。保存接口/CAS/commandId/收据及权限无变化。
