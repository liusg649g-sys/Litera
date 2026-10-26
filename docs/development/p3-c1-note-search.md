# P3-C1 笔记关键词搜索

本阶段仅实现本人已保存笔记的关键词搜索，复用P3-A多对多笔记和P3-B `sources` JSON；不增加迁移、AI服务或PDF全文索引，不触碰5177。

## 契约

- `GET /api/v1/notes/search?q=&page=&pageSize=`：认证只读；空关键词返回空页。
- 字段：标题、正文、受支持来源块的`originalText`和`translatedText`。
- Unicode字面量部分匹配；英文大小写不敏感；特殊字符没有SQL/通配符含义。
- 结果按笔记唯一并携带完整关联文献摘要、有限命中片段、命中字段和高亮位置，不返回完整正文或sources。
- 输入稳定约350ms后请求，旧响应失效；清空恢复当前文献笔记列表。
- 搜索本身不触发保存；打开结果复用既有`choose`/`flush`草稿保护。

## 数据与兼容性

应用层只读搜索本人Note行，避免SQLite/MySQL JSON方言差异。0007表、索引和来源结构保持不变。该方案面向个人中小规模笔记；大规模全文索引属于后续独立变更。

## 验证边界

自动化使用临时SQLite、Mock前端和临时浏览器服务；5180加载前后复核既有预览数据库和PDF。真实MySQL、5177和P3-C2不在本阶段。

## 实现位置

- `backend/app/notes.py`：`GET /api/v1/notes/search`、`_search_note`、`_search_match`。查询最长100字符，分页默认20/最大50；每条笔记最多6个命中，每段最多160字符。分页后才组装关联DTO，避免为未返回结果执行关联查询。
- `frontend/src/notes.ts`：`NotesApi.search`及独立search状态；350ms防抖、请求序号失效、清空/重试、删除和关联缓存同步，点击结果复用`choose`/`flush`。
- `frontend/src/components/NotesPanel.vue`：面板搜索框、加载/空/错误状态、字段与页码标签、纯文本切片高亮、分页和结果打开。

## 2026-10-25 自动化结果

- 后端搜索+笔记定向：29 passed；优化后搜索定向：3 passed。
- 后端完整回归：354 passed，1条既有Starlette/httpx弃用警告。
- 前端搜索/笔记/来源定向：56 passed；最终相关定向：46 passed。
- 前端完整Vitest：25 files / 180 passed。
- `npm run build`两次通过；仅既有大chunk告警。
- 笔记真实HTTP/临时SQLite Playwright：12 passed，包括大小写、特殊字符、多关系去重、点击打开与清空恢复。
- P3-B来源真实HTTP/临时SQLite Playwright：9 passed / 1个本机私有PDF opt-in用例跳过；实际验证PDF原文和隔离Mock译文命中搜索。
- OpenSpec strict：valid。未运行真实MySQL或真实模型调用。

## 5180 隔离加载

正常停止后联合备份到`Litera-backups/notes-preview-p3c1-20261025-204359`：37文件、12,728,602字节，源/副本逐文件SHA256差异0；两份SQLite均`integrity_check=ok`、外键错误0、head `0007_literature_notes`，1账号/2文献/4笔记/7关系/1来源块一致。仅启动一次，90秒D盘变化约168KB，未触发原10GB保护。5180首页、代理和8003健康均200，OpenAPI包含搜索路由，匿名搜索401；重启后计数/PDF哈希保持。

## 人工验收待办

用户需在`http://127.0.0.2:5180/`以原预览账号验证中文/英文、标题/正文/原文/译文、字段高亮、点击打开、清空恢复、多文献唯一结果及未保存草稿保护。该验收完成前OpenSpec 7.6保持未勾选，不进入P3-C2。
