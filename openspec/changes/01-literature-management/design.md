# Design

## Context

收尾状态（2026-10-15）：P1/P2-A/P2-B及全部UI优化已通过用户实际功能/UI验收；下文P2-A分轮限制属于历史，不覆盖末尾P2-B当前实现。专项MySQL测试日志仍单独补证，本次仅文档核对，不修改代码或归档，下一会话另行启动02。

动机见 proposal.md。初始规划时仓库 frontend/backend/storage 为空，主规格为空。P1认证和P2增量迁移保留既有账号/文献。技术路线见[总体架构](../../../docs/design/architecture.md)。负责人Jensen Zhang；当前功能已验收，历史实现见[P2-B记录](../../../docs/development/p2-b.md)及[P2-A记录](../../../docs/development/p2-a.md)。

## Goals / Non-Goals

P2-A UI优化（2026-10-14）：基于06/07/08截图调整，六列表格单行省略+统一浅色Tooltip，固定阅读/详情/更多（编辑题录、下载），无列设置及P2-B菜单项。品牌栏52px。详情弹窗拆为DocumentInfoPanel单一组件，沿用现有GET/PATCH；默认宽360px、320–520px拖动/键盘约束，并为中央区保留560px可用宽度，剩余空间不足880px则覆盖抽屉，同一组件保留草稿。关闭/切换/普通路由离开先确认未保存修改；过期会话允许直接回登录。上传通知由ElNotification右下角5秒呈现，查看及重试使用真实已有服务。后端/API/数据库不变。

2026-10-14 用户确认分轮交付：P2-A实现文献上传/列表/详情编辑/PDF浏览器预览与下载/主界面基础布局，交付后停止待实际验收。P2-B另行启动分类/组合检索/最近阅读/回收站。P2-A仅创建documents和document_files表；其余01实体后续增量迁移，DTO先返回folderId=null、tags=[]、lastReadAt=null。

**Goals:** 以同一普通用户身份贯穿文件/数据/API，建立可恢复文献生命周期；页面与真实服务一同交付，独立验收 P1/P2。

**Non-Goals:** 不提前创建 02–06 数据表，不接自动解析、不扩展管理员、共享或高级导入。

## Decisions

1. 使用服务端可撤销 Cookie 会话与 Argon2id 密码哈希；相比 localStorage JWT 更适合同源 PDF 请求和真实退出。CSRF/Origin 校验与错误包络统一，详情见 [API](../../../docs/design/api-contracts.md)。users/sessions 在 P1 迁移创建。
2. PDF 私有存储和归属绑定，文件名不作路径；SHA-256 + 同用户唯一约束处理并发重复，覆盖回收站。相比仅按题名/DOI 阻断更可靠，也避免跨用户存在性泄漏。P2 处理文件发布/DB 失败补偿。
3. 数据采用单层文件夹/多标签，手工元数据 CAS 更新；具体字段/索引见 [数据模型](../../../docs/design/data-model.md)。单层满足首版分类，嵌套树暂不增加复杂移动/循环规则。
4. 软删除与显式永久删除分离，无自动清空；永久清理使用可查询 cleanup_job，失败重试。相比直接 DB cascade，能观察本地文件/未来向量清理失败。
5. parseStatus=not_requested，仅定义 DocumentUploadedV1；05 接入后再加持久作业，不做请求内模拟解析。
6. P2 实现库导航伸缩和数据表格，样式/菜单/路由见 [UI](../../../docs/design/ui-guidelines.md)。01 文献查看用浏览器真实预览，P3 后才启用在线阅读按钮。

## Risks / Trade-offs

- [会话写请求被伪造] → Cookie 属性、CSRF、Origin 校验及跨站负例测试。
- [文件/DB 无统一事务] → 临时文件、原子发布、补偿与清理作业；上传失败测试。
- [分类/关联越权] → 所有嵌套 ID 复验 owner；两用户集成测试。
- [首次 LIKE 搜索较慢] → 索引/分页/参数化查询；容量确定后再评估全文索引。

## Migration Plan

P1已完成。P2-A新增0002_documents，P2-B新增0003_library分类/打开记录/清理表；已完成临时SQLite升级保留和生命周期测试，用户部署时由API启动迁移。真实MySQL专项证据单独跟踪。回退前联合备份MySQL与私有PDF卷，不删除已有卷；本次不执行迁移或Docker部署。

## Open Questions

本轮已确认上传默认50 MiB（MAX_UPLOAD_BYTES）、Element Plus Icons、自有Logo、侧栏默认240px且180–320px可调，折叠56px。JSON写入保持CAS；FormData不手工设置Content-Type。新增GET /library/config返回服务端实际上限。P2-A暂不接收folderId/tagIds或组合检索；调用未就绪分类筛选返回明确错误，前端不发起这些请求。

文件用pypdf校验结构和至少一页，不提取正文或题录，pageCount仍null；加密/损坏PDF返回415，先解密再导入。单Range实现206/416，多Range首版返回416。私有命名卷只挂载API，Nginx不提供文件静态路径；代理禁用请求体缓冲，API在multipart解析前限制请求流至配置文件上限+64KiB封装开销，并逐文件严格执行配置上限。

上传在同私有目录暂存、fsync、DB flush唯一约束、原子发布、commit。失败回滚并补偿；若提交已成功但确认丢失，保留已提交文件并返回失败，让用户刷新/重复检测确认结果。文件系统与数据库无统一事务：进程被强制终止可能留下未引用文件，P2-A不宣称具有崩溃恢复作业；部署须联合备份PDF卷与数据库。自动化使用临时SQLite及真实本地HTTP，不替代MySQL/容器用户验收。

Q1/Q2的上传上限、图标和导航宽度已确认。Q7排期/目标容量仍待确定。D1–D5已落实到01现有业务，未来关联清理在对应模块接入；用户功能/UI验收已通过，专项MySQL日志仍待补证。


## P1 登录注册优化决定

采用Element Plus原生validateField和submit校验：关闭规则变化自动校验及输入组件默认校验事件，只在非空失焦/提交时验证；修改清除对应提示，标签切换nextTick后clearValidate。保持现有字段与认证安全契约。

主题集中于frontend/src/theme.css，主色#9B0000、hover#B82A2A、active#750000，Logo内联SVG继承Token。仅映射Element Plus品牌变量，不覆盖状态色；正文样式引用变量，其他模块可直接复用。

保留原有分栏；缩减卡片/表单间距、预留字段错误空间，注册保留min-height，登录使用内容高度及顺序布局，不拉伸居中表单；允许切换时卡片按内容改变高度，窄屏自然滚动。用本地Vite隔离UI测试覆盖布局及触发时机，既有8080服务另测真实认证；不构建或启动Docker、不修改后端认证、不提交或推送。


## P2-B当前落地（2026-10-14）

用户已明确启动并完成本轮01 P2-B代码：0003_library增量迁移、个人分类、组合检索、已打开进度子集/历史、软删除/恢复/清理状态与显式重试、原UI真实接入。新增兼容接口POST /cleanup-jobs/{jobId}/retry及nullable DocumentDTO.cleanupJob，仅影响01；具体行为、真实测试与手动MySQL验收见docs/development/p2-b.md、api-contracts.md和HANDOFF。保留P2-A段落为阶段历史，本轮不改变02–06的分工或启动边界。

## P2-B局部交互优化（2026-10-15）

更多菜单移动/管理标签改用DocumentClassifyDialog小窗口，复用LibraryActionDialog与既有PATCH，只写version+folderId或tagIds；GET载入最新文献和本人分类，冲突保留选择并显式读取最新版本。同篇已打开面板通过sync更新DTO/基线，其他文献面板不被替换；有草稿时仍用既有局部确认。ElSelect/Option和CheckboxGroup复用现有Element Plus，无新依赖；空字符串是未分类/全部文件夹的有效选择，显式empty-values排除空字符串以显示正确名称。

关键词/筛选300ms防抖，立即取消旧请求并递增revision；更新保留旧结果与轻量状态，初次/切换视图才显示完整加载。保存和手动检索沿用即刻刷新。空结果必要时用既有未过滤GET documents?pageSize=1的真实total判断全库，不缓存猜测，不新增后端；展示依据最后完成的查询，空标签/文件夹提供回库归类指引。只调整前端及UI规约，无后端业务/数据库结构变更。
