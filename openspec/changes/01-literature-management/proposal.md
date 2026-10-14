# Proposal

## Why

Litera 需要一个具有真实身份认证、文件权限和个人数据隔离的文献库，作为其余五模块的数据入口。提出本change时仓库只有空目录和OpenSpec配置；现P1认证已实现，P2文献业务未开始。

## What Changes

- 规划并实现普通用户注册、登录、退出和个人资料；不引入管理员、第三方/短信登录。
- 规划私有 PDF 上传、查看、下载、重复检测、手工题录、文件夹、标签、检索筛选排序、最近阅读、回收站恢复与永久删除。
- 按登录页→文献库分阶段实施，页面和真实 API/数据库/权限同步验收；上传预留 parseStatus 与 05 的扩展契约。
- 公共架构/UI/API/数据/协作方案见 `docs/design/`。本轮已实现P1账号认证；P2文件/文献服务仍保持规划状态。

## Capabilities

### New Capabilities

- `user-auth`: 普通用户身份、会话生命周期、资料与认证边界。
- `literature-library`: 私有 PDF 文献生命周期、元数据、分类、检索和回收站。

### Modified Capabilities

无；`openspec list --specs` 未发现现有能力。

## Impact

负责人Jensen Zhang；P1已实现、P2待开发，第一阶段。未来涉及 frontend auth/library、FastAPI auth/documents/folders/tags、MySQL、私有存储、Nginx；为 02/05 提供身份、文献与文件契约。P1 checklist按验收更新，P2实现项仍未开始。具体建议与待确认项见公共 decisions 文档

P1 UI优化沿用本change：首次无错误、非空失焦及提交校验、统一#9B0000主题Token和稳定响应式布局；不新增模块或调整成员分工。
