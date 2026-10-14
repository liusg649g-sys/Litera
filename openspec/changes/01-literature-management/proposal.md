# Proposal

## Why

Litera 需要一个具有真实身份认证、文件权限和个人数据隔离的文献库，作为其余五模块的数据入口。提出本change时仓库只有空目录和OpenSpec配置；现P1/P2-A/P2-B及UI优化已完成，用户已确认实际功能/UI验收通过。专项MySQL自动化证据单独跟踪于tasks 5.A1，不由SQLite结果推断。

## What Changes

用户已确认P2拆为P2-A与P2-B，均已获授权实施并验收；本次只文档收尾和02交接，不归档或启动阅读器。保留稳定documentId与/reader/:documentId占位路由。

- 规划并实现普通用户注册、登录、退出和个人资料；不引入管理员、第三方/短信登录。
- 规划私有 PDF 上传、查看、下载、重复检测、手工题录、文件夹、标签、检索筛选排序、最近阅读、回收站恢复与永久删除。
- 按登录页→文献库分阶段实施，页面和真实 API/数据库/权限同步验收；上传预留 parseStatus 与 05 的扩展契约。
- 公共架构/UI/API/数据/协作方案见 `docs/design/`。用户功能/UI验收已完成；专项MySQL测试需实际证据，不假称已核验。

## Capabilities

### New Capabilities

- `user-auth`: 普通用户身份、会话生命周期、资料与认证边界。
- `literature-library`: 私有 PDF 文献生命周期、元数据、分类、检索和回收站。

### Modified Capabilities

无；`openspec list --specs` 未发现现有能力。

## Impact

负责人Jensen Zhang；P1/P2-A/P2-B及UI优化已完成并通过用户功能/UI验收。涉及frontend library、FastAPI documents、MySQL增量迁移、私有PDF卷与Nginx；为02/05保留稳定文献与文件契约。任务按真实证据更新，专项MySQL补证与归档条件见tasks.md及HANDOFF.md，本次不改业务代码。

P1 UI优化沿用本change：首次无错误、非空失焦及提交校验、统一#9B0000主题Token和稳定响应式布局；不新增模块或调整成员分工。
