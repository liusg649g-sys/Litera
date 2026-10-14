# Design

## Context

动机见 proposal.md。仓库 frontend/backend/storage 为空，主规格为空；无历史数据需迁移兼容。技术路线、目录、部署与 Git 约定见 [总体架构](../../../docs/design/architecture.md)。负责人Jensen Zhang，本模块分 P1 登录页、P2 文献库；本次不实施。

## Goals / Non-Goals

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

后续 P1：基础配置/依赖 → users/sessions 迁移 → API/表单 → 验收并停止。P2：文献与分类/进度/清理表迁移 → 文件/API → 库页面 → 生命周期测试。回退前备份 MySQL 与私有文件卷；不删除现有上传卷。迁移在一次性部署步骤运行，本批不创建或执行迁移。

## Open Questions

公共 decisions.md 的 Q1/Q2/Q7：限制数值、图标素材、排期/容量可在对应阶段配置前确定，不改变 API 结构或任务边界。D1–D5 为本批已提出的设计方案，评审若改动则先更新规约。
