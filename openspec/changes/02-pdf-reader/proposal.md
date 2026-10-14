# Proposal

## Why

文献库需进一步支持在线科研阅读与可恢复标注，并向翻译、笔记和问答提供一致的阅读上下文。参考截图中的多标签、工具栏、分栏和悬浮助手可用来降低成员接入成本。

## What Changes

- 规划 PDF 在线阅读、翻页、缩放、目录、全文搜索、文本选择。
- 规划高亮、下划线、书签、批注 CRUD 和阅读进度持久化。
- 规划多 PDF 标签、左右面板的折叠/拖动、AI 悬浮入口及统一 context/事件。
- 文献编辑仅复用 01 手工题录与本模块标注；不重写 PDF 正文，不实现 03/04/06 的业务。
- 01已通过用户功能/UI验收；本批仅完善交接，后续获明确指令后按P3-A基础阅读、P3-B标注/进度、P3-C工作区与扩展接口实施，当前02仍未开发。

## Capabilities

### New Capabilities

- `pdf-reading`: 私有文献在线阅读、文本选择、标注与进度。
- `reader-workspace`: 多标签工作区、可伸缩布局、面板上下文与悬浮助手状态。

### Modified Capabilities

无；01 的目标规格尚未归档为主规格，本 change 只依赖其契约，不重复定义身份和题录修改。

## Impact

负责人Jensen Zhang；待开发，第二阶段。未来新增 PDF.js 与前端 reader、FastAPI annotations/progress、annotations 数据表；使用 01 content/metadata/owner 权限，输出 ReaderContext、NoteDraft 和引用导航接口。公共规范见 `docs/design/`。
