# UI 规范与阅读器接口

## 实际截图分析

| 截图 | 可观察结构 | Litera 取舍 |
| --- | --- | --- |
| 1.png | 顶部品牌与账户；左侧图标+文字；导入/新建、搜索、标签/更多筛选；表格、横向滚动、分页 | 保留库布局；列改为原文标题、作者、年份、期刊、标签、附件、最近阅读、操作 |
| 2.png | 导入按钮展开两级菜单：文献、文件夹、Zotero、附件等，子菜单含本地、DOI、题录、手动录入 | 第一版仅本地 PDF 可用；DOI、批量文件夹、Zotero、手动录入隐藏或禁用并标“待实现”；不支持 CAJ |
| 3.png | 文献标签及关闭；PDF 两行工具栏；PDF、助手、翻译区域；最右侧功能入口 | 简化为 PDF + 一个右侧活动面板，功能轨切换翻译、笔记、AI；保留目录/标注左面板 |
| 4.png | PDF 与助手双栏；分界处箭头，提示“点击收起” | 用明确按钮折叠与独立拖动分隔条；截图本身不能证明拖动，拖动由本项目需求规定 |
| 5.png | 助手收起后 PDF 扩宽；右下悬浮助手；右侧功能轨仍在 | 收起 AI 时显示可聚焦悬浮按钮，点击恢复上次宽度；不遮挡翻页与选区 |

截图是静态参考，不能证明宽度持久化、键盘行为或服务端能力；以下为本项目新增设计。会员、赠送额度、学科商业翻译、广告、科研绘图、实验设计等入口不纳入范围；不复制 Logo、校徽、绿色品牌及夸张渐变。

## 视觉与反馈

品牌 Litera，中文名“科研文献智能管理与协作平台”。主题变量：`--brand-primary: #9B0000`、`--surface: #FFFFFF`、`--page-bg: #F7F8FA`、`--border: #E5E7EB`、`--text: #303133`。选中状态用文字/小区域品牌色，背景主要白/浅灰。字体使用系统中文无衬线；正文建议 14px，清晰行距，简洁边框与少量阴影。图标统一选择 Element Plus Icons 或 Lucide，最终库见待确认表。

登录页品牌+表单，不使用大红铺底；各控件有标签、键盘焦点和错误提示，错误不只靠颜色。通用状态：loading、empty、error/retry、ready；异步失败保留用户输入。功能未就绪时隐藏或显示“待实现”说明，不发起伪服务请求。

Logo 与顶部品牌栏的英文文字统一为 `Litera`；中文产品名保持不变。浏览器页面标题按“Litera · 登录”“Litera · 注册”“Litera · 文献库”“Litera · PDF 阅读器”命名，阅读器文献标签仍显示文献题名。自有品牌图标沿用现有设计要求。

## 页面与路由

| 路由 | 页面/行为 | 归属 |
| --- | --- | --- |
| /login、/register | 表单切换、校验；成功到 /library | 01 第一页 |
| /library | 我的文献与个人文件夹；搜索、过滤、分页 | 01 第二页 |
| /library/recent | 最近阅读，按本人最近阅读时间 | 01 |
| /library/search | 个人库元数据检索，非外部论文搜索引擎 | 01 |
| /library/tags | 标签管理 | 01 |
| /library/trash | 回收站及恢复/永久删除确认 | 01 |
| /profile | 当前用户资料 | 01 |
| /reader/:documentId | 阅读工作区，其他文献在内部标签切换 | 02 第三页 |

根路径按登录态跳转；受保护路由会话失效回到登录。01 尚未交付 02 时，阅读入口显示“阅读器待实现”，PDF 可经真实查看/下载入口使用浏览器预览；不得假装已有在线标注。未实现模块无独立假页面。

## 布局与状态

库导航建议展开宽度 240px，范围 180–320px；收起 56px，仅保留图标和 tooltip。用户点击按钮改变 collapsed，拖动只在 expanded 状态调宽；保留 lastExpandedWidth，扩回恢复宽度。中央 flex 内容用 min-width:0；操作区换行，表格内部滚动，页面不整体溢出。

阅读工作区：ReaderTabs → ReaderToolbar / AnnotationToolbar → ReaderOutlinePanel + PdfViewport + ReaderSidePanel + FunctionRail。PdfViewport 内有文本层与标注层，加载/失败状态可重试。ReaderOutlinePanel 显示目录、书签、批注入口，可折叠；PDF 右侧单一活动面板承载 translation、notes、ai，避免三栏挤压正文。01 的题录编辑表单可由阅读器信息入口复用。

右面板建议宽度 360px，范围 280–520px；PDF 主区域建议至少 480px。窗口不足时转为覆盖式抽屉，关闭后释放空间；“不足”按可用宽度与最小值计算，不硬编码特定设备。拖动采用指针捕获；分隔条支持键盘箭头调宽并有 separator 语义。所有宽度数值是可调 UI 初值，不是商业规则。

| 输入 | 状态变更 | 可见结果 |
| --- | --- | --- |
| open(ai) | expanded=true、activePanel=ai | 隐藏悬浮按钮，PDF 重排 |
| collapse(ai) | expanded=false、保留 width | PDF 扩展，显示悬浮助手 |
| 点击悬浮助手 | open(ai) | 恢复宽度；焦点回面板标题/输入区 |
| open(notes/translation) | expanded=true、切换 activePanel | AI 内容卸载/隐藏，悬浮按钮不额外占空间 |
| 拖动分隔条 | clamp(width, min, max/可用宽度) | 阅读区跟随重排；不改变文献/页码/选区 |
| 窗口缩小/放大 | clamp 或切换 drawer | 不丢失活动标签/阅读进度，放大恢复可用宽度 |

AI 默认为 collapsed；未实现时悬浮按钮可打开明确的“AI 问答待实现”占位说明，仅验证布局，不生成回答或模拟对话。是否启用未就绪入口由单一功能注册表控制。布局偏好按用户存本机，退出清理用户数据；不把 PDF 文本存到布局配置。

## 组件契约（TypeScript 设计示例，仅文档）

公共 DTO 完整定义见 [api-contracts.md](api-contracts.md)。以下不创建 `.ts` 文件。

```typescript
type PanelKind = 'translation' | 'notes' | 'ai';
interface ReaderSidePanelProps {
  context: ReaderContext;
  activePanel: PanelKind;
  expanded: boolean;
  width: number;
  availability: Record<PanelKind, 'pending' | 'ready' | 'unavailable'>;
}
interface ReaderEvents {
  'context-change': ReaderContext;
  'selection-change': ReaderContext;
  'annotation-change': { documentId: string; annotationId: string | null };
  'panel-toggle': { panel: PanelKind; expanded: boolean };
  'panel-resize': { panel: PanelKind; width: number };
  'save-note': NoteDraft;
  'citation-navigate': { documentId: string; pageNumber: number; chunkId: string };
}
```

布局层只负责开关/宽度，模块自己负责业务请求。切换文献时发新的 context、清空旧选区、取消在途请求；响应携带 documentId/contextRevision，旧响应不注入新标签。多标签按 documentId 去重；关闭当前页签激活相邻页签，最后一页回库；未保存标注需明确保存/放弃，不静默丢失。


## P1 表单交互与统一主题

品牌主色正式确定为#9B0000；英文名Litera、中文名和左右分栏保持不变。共享Token在frontend/src/theme.css集中定义：

| 语义 | Token | 色值 |
| --- | --- | --- |
| Primary | --litera-primary | #9B0000 |
| Hover | --litera-primary-hover | #B82A2A |
| Active | --litera-primary-active | #750000 |
| 浅红背景 | --litera-primary-soft | #FFF4F4 |
| 页面背景 | --litera-page | #F7F8FA |
| 卡片背景 | --litera-card | #FFFFFF |

--brand-primary、--page-bg、--surface为兼容别名。Element Plus的primary、light-3、dark-2分别引用Primary、Hover、Active，其余浅色由主色混合白色得到；错误/成功/警告使用独立语义色。运行时Logo采用内联SVG的currentColor引用主题；静态favicon只用与Primary一致的默认回退值。按钮、链接、标签、焦点和其他页面品牌强调共用Token，不在组件中重复写色值。

| 操作 | 行为 |
| --- | --- |
| 首次进入、聚焦 | 不进行校验、不显示错误 |
| 输入过程中 | 不频繁校验；修改已有错误字段时清除对应提示 |
| 尚未提交时空值失焦 | 保持正常；必填错误在提交时检查 |
| 非空值失焦 | 用Element Plus validateField检查当前格式 |
| 点击提交 | 原生表单统一校验必填项/格式/密码确认，非法请求不发往API |
| 切换登录/注册 | 关闭规则变化自动校验，在下一次渲染后clearValidate；清空密码/确认及过时服务端错误 |

不降低邮箱、密码8–128字符、显示名称1–80字符和确认密码规则，不改变后端认证、Cookie/CSRF/Origin逻辑。修改密码后清除过时确认提示，下一次失焦/提交再核对。

桌面保留左右分栏，注册卡片保留最小高度；登录卡片按内容自然撑高，标题、说明、字段、按钮和注册入口顺序排列，不通过拉伸表单产生大块留白。两种模式保持相同视觉风格，允许切换时卡片高度随内容变化；压缩页头、内边距、标签及表单间距，字段底部预留错误提示空间。1280×720、1366×768、1920×1080的正常注册页无纵向滚动且按钮首屏可见；字段错误出现不改变按钮位置。宽度不足时隐藏左侧介绍并采用单栏，低高度允许自然滚动，禁止overflow:hidden裁切表单。

验收：首次及聚焦无红框；非空失焦错误、纠正清除、提交拦截、两种模式切换；合法提交DTO和服务端错误保留输入；Logo/按钮正常、hover、active、标签、链接及焦点颜色；语义状态色独立；三种桌面尺寸及390×844/360×560窄屏；前端构建、UI浏览器测试和现有真实认证回归。

本轮验证结果见 [UI验收记录](../development/p1-ui.md)。
