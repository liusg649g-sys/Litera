# P3-C1 用户反馈修复：原生注释正文与双模式气泡

## 验收结论（当前）

2026-10-17用户明确确认P3-C1验收通过，并补充5.5已在Google Chrome和Microsoft Edge测试，导出内容均正常显示。
本轮以用户确认的Chrome/Edge作为5.5人工验收范围，5.1–5.6全部完成，Change 02为30/36。
Adobe Acrobat Reader未测试、Chrome/Edge具体版本未提供；均不补造为通过证据。真实MySQL专项仍未补证。
C2及03–06未启动，本次仅整理文档与交接，不进行业务开发、Docker操作或Git提交/推送/同步/归档。

下方各修复批次的“等待验收”属于当时状态，不能覆盖本次用户确认。

## 下载入口合并与文件命名

阅读器工具栏改用下载图标+下拉箭头，菜单第一项“导出带批注 PDF / 包含当前已保存的批注”，
第二项“下载原始 PDF / 保留上传时的原始文件”，移除仅承载导出的更多按钮。
窄屏批注抽屉复用PdfDownloadMenu，避免遮挡导致下载入口不可达；导出进行时仅禁用导出项，
原件下载仍可用。沿用现有原件下载授权接口和导出草稿/快照/取消/失败机制。

原件使用上传时文件名，例如“基于双目视觉的水下场景三维重建.pdf”；
导出命名改为“基于双目视觉的水下场景三维重建_带批注.pdf”（下划线，不是连字符）。
服务端UTF-8 Content-Disposition负责命名，不修改原文件或存储键。

验证：类型/生产构建通过，后端导出33/33（隔离SQLite），生产Chromium C1五例通过，
覆盖菜单两项说明、中文原件名/导出名、原件字节一致、成功通知、窄屏草稿、取消/重试/冲突。
OpenSpec严格6/6和git diff --check通过。证据`.cache/c1-menu-build.log`、
`c1-menu-backend.log`、`c1-menu-browser.log`、`c1-menu-openspec.log`。
部署需手动更新API/nginx；未运行Docker、Git提交或归档。

## 导出通知交互修订

按用户反馈，导出状态由通栏改为顶部居中的轻量白色浮动通知，圆角和阴影沿用批注保存提示，
不占据文档布局高度；窄屏限制宽度并允许换行。成功显示绿色完成图标，3秒自动收起且可手动关闭。
处理中、失败及草稿选择不自动消失，保留取消、重试、处理草稿等操作；切换阶段会清理成功计时器。
导出请求、快照、保存与PDF生成逻辑不变。

验证：前端类型检查/生产构建通过（`.cache/c1-toast-build.log`）；生产Chromium C1五例全部通过
（`.cache/c1-toast-browser.log`），包括浮动定位/水平居中/顶部16px、成功自动收起、窄屏草稿保留、
失败重试/重复点击拦截/取消、版本冲突恢复及注释气泡回归。已检查成功和窄屏草稿截图。
运行环境为临时SQLite；本次未修改后端，未重跑后端全量测试。

## 2026-10-17：修复导出文件出现额外注释图标

用户在Edge反馈原注释之外出现额外气泡。已用公开生成样本在隔离Edge
155.0.4283.45原生PDF阅读器复现：水印的Stamp语义批注即使AP为空，Edge仍会
额外显示评论指示图标。原Text注释的位置及Popup双向关联并未产生重复对象。

水印正文语义改为FreeText，与自由文本一致，保留完整Unicode Contents及Popup；
可见水印仍使用原页面内容叠加，原注释外观与交互不变。没有新增附录、接口或迁移。

新增可重复检查脚本`scripts/check_pdf_export_edge.py`：在同一公开样本上生成
移除水印语义批注的对照文件，以及恢复Stamp的旧版探针，再分别交给原生Edge打开。
第一页面内容区域像素对比：修复版与对照完全一致；旧版出现15×16像素的额外图标。
结构检查同时确认4页共4个Text注释和8个FreeText（自由文本/水印），正文仍完整保留。
证据在`.cache/c1-acceptance/edge-regression.json`、`all-13-annotated-edge.png`、
`edge-fixed-diff.png`及`edge-legacy-diff.png`，并已检查修复后原生Edge截图。
此检查为自动化原生Edge回归，不替代全部13类对象的Edge/Adobe人工兼容验收。

复现命令（Windows CMD，已安装开发验证依赖、前端依赖及Edge）：

```cmd
backend\.venv\Scripts\python scripts\create_pdf_export_samples.py
backend\.venv\Scripts\python scripts\check_pdf_export_edge.py
```

部署后需要重新导出；旧文件不会自动修复。手动检查用户反馈的两篇文献：
注释仅在原位置显示，水印附近不再出现额外气泡，点击原注释仍能看到正文。
原文件SHA-256保持不变；生成样本仍为13类×4页、4页导出为4页。

本次最终回归：后端181/181（隔离临时SQLite，77.07秒，非真实MySQL），
日志`.cache/c1-stray-backend.log`；补强原生批注参数化测试，明确comment为Text、
自由文本和水印为FreeText且空AP，保留Unicode正文与Popup关联。
OpenSpec严格校验6/6，日志`.cache/c1-stray-openspec.log`，`git diff --check`通过。
本补丁没有修改前端，前端证据沿用下方前次批次，不冒称本轮重新执行。

日期：2026-10-17。仅C1验收修复；不进入C2，不改B1/B2保存、CAS、收据、撤销或数据库。

## 产品决定与根因

用户明确要求：导出不生成末尾附录；注释应在原位置查看正文。Litera中同时提供
鼠标悬浮显示/移走消失、单击固定显示/点击其他位置关闭，出现及消失动画均100ms。

首轮实现把注释气泡画成页面内容，仅把正文写在附录，没有PDF /Text /Contents，
因此第三方无法在气泡处弹出正文。首轮“附录可见”的自动化并不能证明原生注释可交互，
此缺口按本次反馈修复。旧方案、旧批次数字保留于首轮记录，不能充当本次人工验收。

## 当前导出

导出页数严格等于原页数。注释使用标准Text注释，完整Unicode /Contents和Popup双向关联，
有确定的自定义AP外观；仅画一次气泡，不再添加附录编号。自定义外观复用原颜色/透明度，
按CropBox/Rotate/UserUnit映射；旋转页保持气泡正立，页边翻转不越界。
注释设置正确的/F打印标记，未写入脚本、动作或富文本。原PDF已有批注保留。

其他12类保留原页面内容叠加与zIndex顺序。自由文本与水印在原框内显示，
完整正文额外写入标准FreeText（自由文本及水印）批注及Popup；其语义层使用空AP，不重复绘图或改变层叠。
不要求阅读器自行生成中文外观，也不承诺第三方原生编辑与Litera完全一致。
即使自由文本超框，完整正文仍在PDF批注数据中，用户可在支持的阅读器批注面板查看。
具体第三方弹出/批注面板支持仍需Edge/Adobe实际验收。

## Litera浏览器交互

- 页点及文本选区注释共用一个气泡；悬浮出现，移出锚点关闭，淡入/淡出各100ms，无额外等待。
- 单击注释固定气泡，鼠标移走及悬浮其他注释不替换它；单击其他注释切换固定内容。
  点击PDF空白、其他控件或按Esc关闭；点击气泡内保留，以便滚动/复制较长正文。
- 原点击定位批注列表、原位编辑、移动/删除继续保留；保存机制未改。
- 气泡跟随当前PDF页面位置，支持滚动、布局重排；离屏释放、对象删除、切文献/卸载清理引用。
  内容以纯文本显示，保留换行；不会把用户的HTML当标签执行。
- 导出PDF重新在Litera打开时，从PDF.js读取原生Text批注的正文/矩形并复用同一交互。
  只读展示，不把原生批注复制成新的Litera对象，不改导出文件。

100ms与单击固定属于Litera控制的界面；Edge、Adobe等第三方的触发方式、动画、
是否需要打开批注面板由阅读器决定，不能通过PDF文件强制统一，也未宣称已人工通过。

## 验证与人工验收

已生成新版`.cache/c1-acceptance/all-13-annotated.pdf`：4原页/4输出页、52对象，
原件SHA-256仍为`dfa8ed68d2dc0a6ff126d61b1a42fddb7f5565aec8a3d4fa0a7b200f68218c4b`。
样本覆盖13类、0/90/180/270、CropBox偏移、UserUnit=2、中文/英文/符号/换行/透明PNG及JPEG。
MuPDF 1.26.7独立结构与局部渲染检查通过。生成及渲染小样本0.610秒、peak working set107.4MiB、
109910字节；不外推极端文件性能。新版普通页已目视检查。

修复中曾遇到：类型声明没有convertToViewportRectangle，改为实际支持的两个点变换；
测试中BooleanObject不能直接按Python bool取值，改为检查.value。中间失败批次不算通过。
最终批次见本节末尾补充。

Windows CMD由用户手动部署（本轮未执行）：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
```

同时更新API/nginx后Ctrl+F5。已有批注不必重建，但旧导出文件不会自动更新，需要重新导出。

1. 在当前文献分别悬浮页点/选区注释，确认显示正文，移走后100ms淡出。
2. 单击注释后移走鼠标，正文持续显示；点击气泡内不关闭，点击空白关闭。
   单击另一条切换内容；检查批注列表仍正常联动、编辑保存/取消及撤销不回归。
3. 重新导出，确认页数与原件一致，没有附录；原件再次下载的SHA-256不变。
4. 分别用Edge PDF与Adobe Reader打开新版导出，检查注释图标及正文弹出/批注面板，
   记录应用版本、日期和结果。自由文本/水印超框的全文也应在原生批注正文中。
5. 如第三方只支持点击或侧栏，记录实际触发方式；不将Litera双模式交互当成第三方人工通过证据。

Edge/Adobe人工结果、真实MySQL专项及用户实际UI验收均待执行。tasks 5.5/5.6保持未勾选。


## 最终批次证据

- 完整后端181/181（临时SQLite，非MySQL），日志`.cache/c1-popup-final-backend.log`；
  导出专项33例含原生Text/FreeText（自由文本及水印）完整Unicode正文、Popup双向关联、AP、原批注保留及原页数不变。
- 前端类型检查/生产构建通过，日志`.cache/c1-popup-build2.log`；Vitest13文件62/62，日志`.cache/c1-popup-unit.log`。
  原有约549kB ReaderPage chunk提示非阻断。
- 生产Chromium真实PDF合并9/9（C1五例+B1/B2四例），日志`.cache/c1-popup-final-browser.log`。
  覆盖导出重新上传、PDF.js读出原生注释正文并悬浮/固定/外部关闭、页数4保持4；
  原有页点与选区注释的双模式、100ms动画样式、文本HTML不执行、列表联动；
  原位编辑/保存取消、六类闭环、跨页/旋转CropBox/50%–500%以及B2七类橡皮擦与持久撤销重做。
- 已检查固定气泡截图`.cache/c1-popup-final-ui/reader-c1-C1-comment-hover-5d7d1-aces-including-text-anchors/pinned-comment.png`。
  原有阅读进度草稿提示来自测试刷新前的未完成进度，并非伪造保存成功；本修复未改变进度机制。
- OpenSpec严格校验6/6；19份相关文档的120条本地Markdown链接目标检查及git diff --check通过，严格校验日志`.cache/c1-popup-openspec.log`。

未运行Docker Compose、业务库迁移、Git commit/push或OpenSpec archive。Edge/Adobe真实人工验收仍待用户执行。
