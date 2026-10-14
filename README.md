# Litera

**科研文献智能管理与协作平台**，为《互联网软件开发技术与实践》课程小组项目，采用 OpenSpec 规约驱动开发。

英文项目名称及 GitHub 仓库名称：`Litera`。

项目围绕科研文献的导入管理、PDF 阅读、翻译、笔记、信息提取和 AI 问答组织六个模块。当前规划普通用户端，以 Litera 自有品牌和北大红为视觉基调。

## 当前进度

已完成系统设计和六个模块的 OpenSpec 规划，尚未开始业务开发。各 change 已包含 proposal、design、specs 和 tasks；实现任务全部未勾选，规约完成不代表模块已实现。

## 技术方案

采用 B/S 架构、前后端分离。

| 层次 | 技术 |
| --- | --- |
| 前端 | Vue 3 + TypeScript + Element Plus |
| PDF 阅读 | PDF.js |
| 后端 | FastAPI |
| 数据与文件 | MySQL + 本地私有 PDF 存储 |
| 文献解析 | PyMuPDF |
| 智能服务 | 大语言模型 API + RAG |
| 部署 | Docker Compose + Nginx |
| 测试 | pytest、前端测试与接口测试 |

开发环境：Windows + CMD + Docker Desktop；版本管理：Git。以上是规划技术路线，运行命令在对应阶段实现后补充。

## 成员分工

| 成员 | 负责模块 |
| --- | --- |
| Jensen Zhang | 文献管理、PDF 阅读与文献编辑 |
| Siguo Liu | 文献翻译、文献笔记 |
| Jialu Ma | 文献信息自动提取、AI 文献智能问答 |

六个模块的功能简介见 [OpenSpec change 总览](openspec/changes/README.md)。

## 仓库目录

```text
frontend/        前端代码（待开发）
backend/         后端代码（待开发）
storage/         本地私有文件存储（待开发）
scripts/         辅助脚本（待开发）
docs/design/     系统架构、UI、API、数据模型与验收设计
docs/references/ 界面参考截图
openspec/changes/六个模块的独立 change
openspec/specs/  主规格，后续按工作流同步
```

## 开发顺序与文档

后续按 **注册登录页 → 文献库主界面 → PDF 阅读器** 逐页实现和验收。翻译、笔记、信息提取、AI 问答分别由对应成员后续接入；各模块遵守统一认证、API 和数据隔离契约。

- [设计文档索引](docs/design/README.md)：架构、UI、API、数据模型与依赖。
- [开发与验收计划](docs/design/delivery-plan.md)：阶段顺序和验收条件。
- [设计决策与待确认项](docs/design/decisions.md)：重要建议及后续配置选择。
- [规划校验记录](docs/design/validation.md)：OpenSpec 严格校验结果。

本期范围为普通用户文献管理与阅读辅助；管理员后台、跨用户共享等扩展需独立规划。
