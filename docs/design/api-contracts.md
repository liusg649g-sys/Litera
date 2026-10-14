# 统一 API 与跨模块契约 v1（Change 01 已实现，02–06 规划）

本文件为统一API契约。Change 01 的认证、文献、分类、检索、最近阅读及回收站已实现并通过用户功能/UI验收；02 的实际页码/缩放与标注、03–06 接口仍为规划。API 前缀 `/api/v1`；JSON 使用 camelCase、UTF-8。所有 ID 为不透明 string（实际 UUID），时间为 UTC ISO 8601，展示使用本地时区；物理 PDF 页码从 1 开始，不等同印刷页标签。

## 通用约定

### P2-B 当前实现（2026-10-14）

Change 01表中的分类、检索、最近阅读、回收站已实现。列表允许title/year/createdAt/lastReadAt排序；q搜索标题、作者、摘要、关键词、DOI及期刊，参数化LIKE并转义通配符；tagIds逗号分隔全部匹配，年份1–9999且区间有序。重复或未知查询参数422，分类归属错误404。文件夹/标签名称NFKC、trim、casefold后用户内唯一，1–100可见字符；标签color可空或#RRGGBB。GET /folders和/tags返回DTO数组。

PATCH增加folderId（null未分类）和tagIds（null/[]解除全部关联），省略保持；题录和分类通过同一version CAS原子保存。分类删除同时解除回收站文献关联并递增受影响文献版本，不删除PDF。

01实际提供GET/PUT /documents/{id}/progress的已打开子集：PUT `{}`更新服务器lastReadAt和progress.version，重复打开更新同一记录；GET内容/列表/下载不写历史。pageNumber/zoom非null返回503 READER_NOT_READY；可选version校验冲突409。GET /reading-history支持与文献列表相同过滤，始终按lastReadAt倒序（sort/order仅校验），返回既有document/progress分页包络。不实现02真实页码/缩放。

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

## Change 02：阅读与标注（目标契约，除打开记录子集外待实现）

| 方法/路径 | 输入 | 输出 |
| --- | --- | --- |
| GET /documents/{id}/annotations | 可选 pageNumber | AnnotationDTO[]；覆盖书签/批注 |
| POST /documents/{id}/annotations | `{type,pageNumber,position,selectedText?,content?,color?}` | 201 AnnotationDTO |
| PATCH /documents/{id}/annotations/{annotationId} | `{content?,color?,version}` | DTO；类型和锚点不可改变，重新选区创建新标注 |
| DELETE /documents/{id}/annotations/{annotationId} | 无 | 204 |
| GET /documents/{id}/progress | 无 | ProgressDTO 或未读默认值 |
| PUT /documents/{id}/progress | `{pageNumber?,zoom?,version?}` | ProgressDTO；01 打开只记 lastReadAt，02 页码已知时保存实际状态 |

页码校验依据 PDF.js 获得且后端验证的物理总页数；01 不依赖 PyMuPDF 自动解析，后续 02 可使用轻量 PDF 结构库读取页数。仅记录打开时间的空请求不修改页码/缩放；提交页码或缩放必须带 version，未读默认 version=0，首次保存以0创建，后续CAS递增，旧版本返回409。客户端遇409读取最新版；页面离开前提交但不把网络失败当成功。

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

UserDTO、DocumentDTO、分类和打开记录已有实现；ReaderContext、SelectionPosition、AnnotationDTO、NoteDraft、Citation及03–06 DTO是待落地的公共契约，不代表仓库已有对应类型或接口。ProgressDTO.zoom对外为number/null；现有ORM为nullable VARCHAR(20)，读取时转float，02应明确合法范围及写入转换，不重复创建reading_progress。

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
interface AnnotationDTO {
  id: string; documentId: string; type: 'highlight'|'underline'|'bookmark'|'comment';
  pageNumber: number; position: SelectionPosition[] | null;
  selectedText: string | null; content: string | null; color: string | null;
  version: number; createdAt: string; updatedAt: string;
}
interface ProgressDTO {
  documentId: string; pageNumber: number | null; zoom: number | null;
  lastReadAt: string | null; version: number;
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

NormalizedRect 相对于 PDF 未旋转页面，以左上角为原点，x/y/width/height 位于 0–1，边界不能越出页面；缩放、设备像素比和旋转在 PDF.js 适配层转换，不持久化 CSS 像素。多页选区按页数组，ReaderContext.pageNumber 为选区起始页，未选中文本时 selectedText=''、selectionPosition=null。书签 position 可 null；高亮/下划线必须有非空 rects，comment 可页级或选区级。手工及未形成批注的选段笔记 sourceId 可 null，选段须有 originalText/有效页码；翻译与AI笔记 sourceId 必须为本人同文献的 translationId/answerId。

TextChunk 只跨一个物理页，offset 按提取页文本的 Unicode code point 计数，半开区间 `[startOffset,endOffset)`，不依赖 JS UTF-16 索引；跨页内容用多个 chunk 和多条引用表达。引用 pageNumber/quote 必须能在对应版本页文本核对，服务端校验证据，客户端不信任模型随意编造的页码。

## 上传扩展点与接入事件

内部 `DocumentUploadedV1={eventId,documentId,ownerId,fileHash,storageKey,occurredAt}` 仅在存储与 DB 提交成功后可发出。storageKey/ownerId 不进入公开 DocumentDTO。01 定义契约且 parseStatus=not_requested；05 启用后可靠入队 queued，并按 `(documentId,fileHash,eventId)` 幂等消费，读取文件前再次校验文献有效。完成提取原子发布版本，禁止部分 pages/chunks 被 06 读取。

`ExtractionReadyV1={documentId,ownerId,extractionVersion,fileHash}` 通知 06 建索引；索引就绪前回答 503 INDEX_NOT_READY，不编造答案。文献软删除时取消/屏蔽在途任务；永久删除清理正文、chunks、向量与来源记录。ReaderEvents 见 UI 文档，context-change 是最新值快照，contextRevision 在切换文献/页码/选区时递增。
