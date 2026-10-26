# P3-B：PDF 原文与翻译结果保存到笔记

## 范围和环境

本轮在既有 Change 04 与 P3-A 多对多笔记基础上增量实现来源摘录。开发基线为 `local/litera-dev-20261020`、`947dc3cc6381ce4b19d587762950f381b6e31100`。实际加载环境仅为隔离预览 `http://127.0.0.2:5180/`，其 API 为 `127.0.0.1:8003`、数据库为 `.cache/notes-preview/preview.db`。原 5177 数据库保持迁移版本 `0006_reader_assets`，未执行 0007 或任何 P3-B 写入。

本轮不增加表、列或索引。复用 0007 中 `notes.sources` JSON、`source_schema_version=1`：`notes.content` 仍是用户可编辑的纯文本；PDF 摘录和翻译摘录是独立、只读的结构化来源块。两者不会因编辑正文或解除笔记与文献的关联而被改写。

## 后端实现

- `backend/app/note_captures.py`
  - `POST /api/v1/notes/captures` 原子完成“新建笔记并插入来源块”或“按 version CAS 向已有笔记追加来源块”。
  - `GET /api/v1/notes/capture-config` 公布非敏感限额和预览 Mock 标识。
  - `validate_pdf_source` 从服务器保存的 PDF 重取页面文本，核对页码、原文、字符可靠性和不透明字体映射；异常 PDF、越界页码或无法在页面中核对的文字均拒绝保存。
  - `make_block` 快照文献 ID、标题、文件 SHA-256、实际 PDF 页码、选区元数据和 `contextRevision`。选区矩形仅作为语法校验后的页级定位元数据，不声称服务器已验证精确坐标。
  - `associationMode=link|keep` 明确决定是否把来源文献加入笔记关联；不会静默改变多对多集合。
  - `operationId` 和请求指纹提供幂等回放；相同 ID 不同内容返回冲突。已有笔记使用 version CAS，块数和 JSON 字节数有界。
  - MySQL `REPEATABLE READ` 边界：首次幂等探测未命中后先 `rollback()` 结束旧一致性快照，再按文献、笔记顺序加锁并二次探测；现有笔记和同 ID 新建笔记的并发请求均只保存一个块和一条关联。
- `backend/app/translation_proof.py` 为短期翻译回执签名和校验。签名绑定用户、文献文件哈希、页码、原文、译文、方向、上下文修订和规范化模型输入，API Key 和签名密钥不返回前端。
- `backend/app/translations.py` 在翻译响应中返回 `translationProof` 和 `translationProvenance`。正常服务标记 `model_api`；仅 `APP_ENV=test` 且显式启用隔离夹具时标记 `isolated_mock`。
- `backend/app/notes.py` 注册摘录路由，并允许按标题过滤个人笔记候选。所有读取、写入、关联和来源保存继续校验会话、CSRF、笔记 owner 与文献 owner。

来源块当前格式包含稳定块 ID、类型、创建时间、原文、来源快照和历史标记；翻译块另含译文、方向及翻译来源。`requestFingerprint` 用于同一操作幂等，不作为用户内容展示。

## 前端实现

- `frontend/src/reader/noteCapture.ts` 从 ReaderContext 构造 PDF 原文摘录；保留原始选择、页码、位置和上下文修订，沿用 P2 异常文字保护。
- `frontend/src/components/SaveToNoteDialog.vue` 提供新建、当前笔记和个人已有笔记三种目标，支持标题搜索；目标未关联来源文献时必须显式选择“建立关联”或“仅保存来源”。请求失败保留原选区/译文和对话框，可安全重试。
- `frontend/src/components/NoteSourceBlocks.vue` 把用户正文与 PDF 原文/翻译来源卡分开显示，展示文献标题、PDF 页码、方向和 Mock 标记；只用 Vue 文本绑定输出外部文字。
- `frontend/src/components/NotesPanel.vue` 与 `frontend/src/notes.ts` 在保存前协调自动保存、当前笔记版本和关联列表，成功后以服务器 DTO 刷新；正文编辑不修改来源块。
- `frontend/src/components/TranslationPanel.vue` 只允许保存带服务器回执的结果。结果仍匹配当前 ReaderContext 时作为当前译文保存；选区或文献已变化时，必须明确确认保存历史结果，并使用该结果自身的文献、页码和原文。
- `frontend/src/views/ReaderPage.vue` 接入 PDF 选区“添加到笔记”和翻译结果“保存到笔记”。保存操作不会清空选区、译文或失败状态，也不改写已保存来源。

## 数据兼容和备份

P3-B 不需要新迁移，因此 0007 中已有的空数组、旧笔记正文和关联记录保持兼容。来源 JSON 的版本仍为 1；遇到未知版本或正文格式时服务端返回 409，不自动改写。

5180 加载前，预览服务已因既有磁盘保护自动停止。只读检查确认其数据库仍为 0007、完整性 `ok`、外键错误 0，且与最后运行快照的所有业务表行哈希和 PDF 哈希一致。随后把整个 `.cache/notes-preview` 复制到：

`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3b-20261023-191156`

备份共 9 个文件、12,660,913 字节；源和目标逐文件路径、大小、SHA-256 一致，备份数据库完整性 `ok`、外键错误 0，两份引用 PDF 均存在。备份失败时的处置是停止加载并保留源目录，不用备份覆盖当前库。

## 自动化验证

所有后端业务测试均使用隔离临时 SQLite 和 Mock，不连接 5177/5180：

- P3-B 最终组合：122 passed、1 个既有 Starlette/httpx 弃用警告、39.28 秒。范围为 42 个摘录、26 个笔记、37 个翻译、17 个 PDF 文本测试。
- 0006→0007 迁移兼容：3 passed，覆盖临时 SQLite 升级/重复升级/旧行资产保持和 MySQL 离线 DDL 类型；这不是实际 MySQL 测试。
- 文献、批注和导出回归：118 passed；此前误写不存在的 `test_pdf_export.py` 命令退出 4，修正为 `test_pdf_exports.py` 后才取得该结果。

前端：

- Vitest 全量 24 个文件、176 tests passed。
- `vue-tsc --noEmit` 通过。
- `npm run build` 通过，1706 modules；仅保留大于 500 kB 的现有 chunk 警告。
- P3-A 笔记浏览器回归 11 passed。
- P3-B 隔离浏览器 9 passed，使用真实 HTTP、临时 SQLite、PDF.js 与合成 PDF；翻译为显式 `isolated_mock`。覆盖新建/当前/其他笔记、关联/不关联、跨文献来源、解除关联后来源保留、当前/历史译文、迟到结果、丢失响应幂等、异常 PDF 和重登持久化。
- P2/阅读器浏览器组首次为 27 passed、1 skipped、1 failed；失败是 Mock 返回过快而未观察到瞬时加载文案，最终译文已正确。测试夹具加入可控响应闸门后，该失败用例定向复跑 1 passed。没有把这次定向复跑描述为整组重跑。

真实模型未在 P3-B 测试中调用；真实 MySQL 也未执行。预览明确显示隔离 Mock，不能作为真实翻译质量证据。

## 实际预览加载

2026-10-23 完整备份后只启动 5180/8003。首页、前端代理健康接口、API 健康接口均返回 200；匿名访问新 `capture-config` 返回 401。日志明确写入“Explicit isolated Mock translation enabled; no real model service is used”。重载前后预览仍为 1 个用户、2 篇文献、3 条笔记、5 条关联，所有业务行哈希和 PDF 哈希不变。

5177/8002 在本轮加载前已被既有磁盘监控自动停止，原因是当时 D 盘曾短暂低于 10 GB；本轮未启动它。其数据库仍为 0006，7 个账号、10 篇文献、8 条批注、1 个阅读器资产及所有业务行/资产哈希与最后运行快照一致。

## 已知边界

- 精确选区矩形仅供后续定位扩展；当前可靠承诺是文献与 PDF 页级来源。
- PDF.js 与 pypdf 的文字顺序可能对复杂多栏页面不同；服务端会保守拒绝无法核对的摘录，不猜测内容。
- 解除笔记与来源文献的关联不会删除来源块；卡片会保留快照，并可显示来源已不在当前关联集合。
- P3-B 未在真实 MySQL 下验证 RR 锁行为，虽有顺序和并发隔离测试，仍需未来独立 MySQL 测试库补证。
- 5177 未迁移、未加载笔记或 P3-B；本轮唯一人工验收入口是 5180。

## 2026-10-23：正常 PDF 摘录误拒修复

人工验收在文献 *Confocal interferometric scattering microscopy reveals 3D nanoscopic structure and dynamics in live cells* 第 1 页稳定复现 `PDF_TEXT_NOT_FOUND`。前端 ReaderContext 提交的页码为 1，原文与 `positions[].textQuote` 经接口契约规范化后完全相同，定位中包含 6 个矩形和 6 个文字范围；当前原文与上一条 Mock 译文各自使用自己的文献、页码、位置及签名回执，没有发生来源状态串线。

实际根因是 `validate_pdf_source` 只用 pypdf 的 `extract_text()` 做规范化后的整段子串比较。该页使用 CFF Type1 字体，PDF.js 与 pypdf 对文字项、跨行空格、标点和选区首尾半词的分段不同；整页文字相似度约 0.989，但大量正常连续选区无法形成相同字符串。临时加入 fontTools 后提取结果不变，因此未把它加入运行依赖。PyMuPDF 对此页匹配较好，但其 AGPL/商业许可不适合作为本项目默认运行依赖，未采用。

修复新增 `backend/app/pdf_source_validation.py`，并加入 BSD-3-Clause/Apache-2.0 的 `pypdfium2==5.14.0` 作为第二个独立服务端提取器。服务端仍先执行现有不透明字体映射和异常字符检查，并只在同一物理页内接受以下证据之一：空白/NFKC 后的精确文本、连续且顺序一致的 Unicode 词序、存在真实换行证据的行尾断词词序。浏览器选区允许仅第一个词从服务器词尾开始、最后一个词在服务器词首结束；所有中间词必须逐词完全一致。缺词、乱序、普通 `label-free` 一类复合词误拼、异常映射和越界页码仍拒绝。保存块继续使用未经改写的浏览器原始选区和原定位数据。PDFium原生API在同一进程中不是线程安全的；最终并发复核实际触发Windows原生访问冲突后，`validate_pdf_source`使用进程内锁只串行化PDFium打开/提取/关闭区段，API事务、权限和CAS逻辑保持原并发行为。

验证结果：

- 后端 `test_note_captures.py + test_notes.py + test_translations.py + test_pdf_text.py`：最终124 passed、1 个既有弃用警告；并发摘录3项连续运行3轮均为3 passed。新增覆盖 NFKC、标点/空格、跨行断词、首尾半词、缺词/乱序拒绝和普通复合词保护。
- 前端 Vitest：24 files、176 passed；`vue-tsc --noEmit` 与生产构建通过（仅既有大 chunk 警告）。
- P3-B 浏览器：10 passed。新增 opt-in 用例把上述本地 PDF 仅上传到 8005/5182 临时 SQLite，实际保存 PDF.js 跨行选区；随后改变选区并保存上一条 `isolated_mock` 译文，核对两条来源各自的原文、文献和页码。异常映射 PDF 拒绝用例继续通过。
- 诊断阶段如实记录：首次后端运行因 PDFium page 不支持 context manager 得到 23 failed/21 passed，改为显式关闭资源后通过；一次最终并发复核在第44项触发PDFium原生访问冲突/进程异常退出，加入上述串行临界区后并发3项三轮与完整124项均通过；浏览器先复现 422，随后两次失败分别来自测试断言错误和测试选词 helper 的 `-1` 边界，修正测试后完整 10 项通过，锁修复后本地PDF定向再跑1项通过。它们不属于业务数据写入。

5180 最终继续使用显式隔离 Mock，不读取 `backend/.env` 或真实 API Key。加载前完整备份为 `D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\notes-preview-p3b-fix-20261023-201043`，17 个文件、12,688,453 字节，逐文件大小/SHA256 一致，备份数据库完整性 `ok`、外键错误 0。一次预加载操作顺序失误曾让 5180 在备份前短暂启动，随即只停止该预览后完成备份；未执行摘录或其他写入测试。备份后的正式重载前后全部表行数/脱敏行哈希以及 2 个 PDF 哈希一致。最终首页、代理健康、API 健康均 200，匿名摘录配置为 401。

5177、Docker、真实模型和 MySQL 均未启动或修改。本节自动化和部署证据不代替用户人工复验，Change04 任务 6.7 保持未完成。
