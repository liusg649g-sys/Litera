# P3-C2-A：笔记来源 PDF 页导航

日期：2026-10-25。范围仅为“打开结构化来源记录中的原始 PDF，并跳到保存的物理页码”；页内文字高亮、坐标重匹配和 OCR 留待 P3-C2-B。5180 隔离预览使用 SQLite 与 Mock 翻译，5177、Docker 和真实模型均不在本轮范围。

## 实现

- `backend/app/documents.py::document_dto` 在受保护的 DocumentDTO 附件信息中返回数据库已有的 SHA256。没有新增表、字段或迁移。
- `frontend/src/reader/navigation.ts::navigateReader` 将 `fileSha256` 作为可靠来源导航标记。它先读取目标文献，核对登录权限、当前附件哈希及已知页数，再调用已注册的 ReaderPage 宿主。ReaderPage 继续负责真实 PDF 加载后的 `numPages` 复核、标签复用和跳页。
- `frontend/src/components/NoteSourceBlocks.vue` 只给具有持久化文献 ID、正整数页码和 64 位 SHA256 的结构化来源显示可执行“查看原文”；旧数据或不完整来源仍可阅读，但明确提示无法可靠定位。
- `frontend/src/components/NotesPanel.vue::openSource` 在跳转前调用现有笔记 `flush()`，保存失败/冲突即停止。跨文献成功后恢复同一条笔记，即使来源文献不在该笔记的关联集合中也不会暗中新增关联。AbortController 与序号防止快速点击的旧请求覆盖新请求。

来源记录保持不可变：导航不修改 `notes.sources`、`note_documents`、标题、正文或译文。来源 PDF 哈希变化、文献删除/越权、页码无效、加载失败均拒绝猜测并返回明确错误。

## 兼容性与风险

DocumentDTO 的 `attachment.sha256` 是只读增量字段，复用上传时已经存储的摘要。前端类型同步为必填字段，现有真实后端均会返回；测试桩需补齐该字段。数据库结构和 0007 迁移保持不变，SQLite/MySQL 都只读取同一列。

如果保存来源后 PDF 内容被替换，即使文献 ID 未变，跳转也会被哈希核验拒绝。旧来源缺失摘要时同样不可跳转；本轮不根据文件名、标题或正文猜测。这是来源可靠性的有意边界。

## 自动化证据

- 后端完整 pytest：354 passed，1 个既有 Starlette/httpx 弃用警告。
- 前端完整 Vitest：25 files / 184 passed。
- P3-B/P3-C2-A Playwright：11 passed，1 个需显式本机 PDF 的既有 opt-in 用例 skipped。覆盖同文献、跨文献、搜索结果、未保存草稿、未关联来源、快速点击与哈希变化拒绝。
- P3-A/P3-C1 Playwright：12 passed。覆盖 CRUD、自动保存、关联、搜索和翻译面板 Mock 回归。
- `npm run build` 与 OpenSpec strict 校验需在最终加载前再次执行；实际结果记录在统一交接报告，不以本节的计划代替。

用户人工验收尚未进行。5180 加载后应检查同文献跳页、B→A 跨文献、关联集合不变、草稿保留和不可靠来源提示；通过前不得进入 P3-C2-B。
