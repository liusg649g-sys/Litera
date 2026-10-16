# P3-A2 阅读器 UI/UX 补充验收

2026-10-15。用户已在Docker部署环境实际体验P3-A2，核心缩放、导航、搜索和进度整体符合预期。本次只处理指定的五类界面问题，仍为02的2.1–2.6补充、12/36，不新增阶段/任务编号，不启动P3-B1。

## 定位与修改

1. 顶部与字体：原品牌/标签/主栏实测52/42/48px，二级栏46px，底栏另占约29px。阅读器改为48/40/40/40px，主/二级栏无纵向padding，控件居中；阅读组仍不挂载二级栏。移除整个Footer，正常保存不常驻状态行，原保存失败/冲突提示和离开保护保留。品牌20px、基础UI12px由theme.css共享Token提供，库/阅读器/标签栏复用；标题及明确字号层级保留。文献库品牌栏仍52px，只同步共享标签40px及相应body高度公式。
2. 箭头：原缩放菜单和大纲使用字符⌄/›，字体度量使视觉尖细且偏心。改为同包Element Plus ArrowDown/ArrowRight SVG，14×14px、相同按钮中心。大纲叶节点保留箭头列宽，层级缩进20px，展开/折叠与原导航逻辑不变。
3. 焦点：原.pdf-viewport:focus-visible在鼠标进入后按方向键也可能触发，形成整个阅读区红框。保留tabindex=0及方向键处理，只在真实Tab导航后显示局部焦点环；阅读区pointerdown清除该标记。没有全局移除outline，输入框方向键仍编辑输入，不翻PDF。
4. 阅读间距：原CSS的24px padding/20px gap与fit函数中的48/20常量分散。统一由zoom.ts的PAGE_PADDING/PAGE_GAP（均12）同时驱动CSS变量、fit宽高及页码/目录位置偏移；三视图一致。双页fit-width扣两侧24px和页间12px，fit-height扣上下24px且取组内最高页；仍限制0.5–5，不改变PDF比例或Canvas/TextLayer/覆盖层的同一viewport。
5. 多余横滚：真实双页fit-width复现scrollWidth=1373、clientWidth=1366，而页面集合本身宽1366。原因是PDF.js的pdf_viewer.css含全局.spread { margin-inline:3.5px }，命中了我们的双页集合。局部.pdf-pages.spread设margin:0去掉额外7px；没有通过overflow-x:hidden掩盖。PDF根容器仍overflow:auto，真实超宽可横向滚动，滚动条改为白灰细样式。工具条/标签条保持横向滚动和键盘可达，隐藏其占高度的滚动轨道以保证40px内部控件不裁切。

fit继续读取实际阅读容器clientWidth/clientHeight，由既有ResizeObserver响应窗口与面板变化，不另外扣导航高度。1366×768单页fit-height修改前容器高597px、页高549px、上距24px；修改后容器高640px、页高616px、上距12px，底部同样12px。正常阅读释放43px正文空间；二级栏出现时恰好占40px，隐藏后归还。

## 修改文件

- frontend/src/theme.css、style.css、library.css：共享字体/标签尺寸Token、库的对应高度公式。
- frontend/src/components/WorkspaceTabs.vue、PdfOutline.vue：标签高度及SVG箭头/缩进。
- frontend/src/reader/reader.css、zoom.ts：紧凑尺寸、12px空间、双页margin冲突、局部焦点/滚动条样式及fit计算。
- frontend/src/views/ReaderPage.vue：移除Footer、共享间距、SVG菜单箭头、Tab/指针焦点标记与监听清理。
- frontend/e2e/reader-layout.spec.ts、playwright.reader.config.ts、tests/reader-a2.test.ts：真实布局回归及更新fit边界样例。

本轮没有修改后端业务、数据库、PDF文件、进度API或保存队列；工作区此前未提交的A1/A2改动全部保留。

## 测试

前端类型/生产构建及Vitest34/34通过。新增真实PDF布局检查覆盖准确栏高、12/20px共享字号、Footer移除、箭头居中/层级/方向、鼠标与Tab焦点、输入框方向键、三视图间距、混合页尺寸双页最大高度、窗口/面板resize、fit恢复后无横滚、500%真实横滚及390px窄屏。

最终生产Chromium阅读器22项分套件通过：布局+A2为9/9，原交互5/5，基础阅读器8/8；文献库22项通过（12+10），覆盖真实上传/题录/原件、分类/检索/历史/回收站/清理故障重试、两用户隔离及窄屏。OpenSpec 1.14.1全部严格6/6、issues=[]，tasks保持12/36（后续24项未勾选）。本轮10份相关Markdown/60条本地文件链接无缺失，git diff --check通过。成功场景沿用真实上传→临时API/SQLite/私有PDF→生产PDF.js，未伪造成功业务；清理故障用例中的PermissionError为预期注入，重试成功，保留历史Node颜色变量警告。后端未改，未重跑后端或MySQL集成测试，不将历史91项SQLite结果当作本次MySQL证据。未运行Docker Compose、实际业务库迁移、commit/push/sync/archive。

截图保存在忽略的frontend/test-results/a2-ux-compact-fit-height.png。原A2完整实现/后端证据见[P3-A2记录](p3-a2.md)。

## Windows CMD 手动验收

仅前端变化，已有环境可只重建nginx，本次未代执行：

```cmd
rem 在项目根目录执行
docker compose up -d --build --no-deps --wait nginx
```

Ctrl+F5后验证：

1. 打开原文献，品牌48px、标签40px、主栏40px；切批注/形状/插入二级栏40px，回阅读隐藏。底部没有Footer，PDF阅读区到窗口底部；库和阅读器Litera均20px、基础文字风格一致。
2. 三模式下看12px边距和页间距；单页fit-height正常桌面上下约12px，双页以最高页适应。开关/拖动面板、调整窗口，fit自动更新且原文比例与文本层正确。
3. 双页fit-width或能容纳的fit-height不应有额外横滚；手动500%或窄窗中真正超宽仍可横向滚动。缩放预设和目录箭头居中，多级缩进清晰、方向正确。
4. 鼠标点阅读区后左右键翻页，无整圈红框；用Tab进入仍有焦点提示。页码/搜索输入框内方向键不翻PDF。
5. 检查缩略图/目录/搜索、Ctrl+滚轮、页码/倍率/视图刷新恢复、标签切换/拖动以及库上传/信息面板/分类/检索。进度错误仍可见并可重试，未完成工具仍只是明确开发中。

交付后停止等待本轮UI验收，不自动进入P3-B1。

## 缩略图清晰度局部补充（2026-10-15）

原因：原PDF.js viewport按128px CSS宽计算，Canvas backing store也仅128px宽，DPR2屏幕将其放大到256物理像素，造成文字与图边缘模糊。既有缓存并未存错版本，而是缓存了低分辨率图。

仅修改PdfThumbnail.vue：viewport仍使用实际CSS显示宽度与PDF原始比例，backing store按CSS尺寸乘devicePixelRatio（限制1–2），通过render transform直接绘制高分辨率图，不把已有低分辨率Canvas放大。视觉宽度仍128px，height:auto和显式原始aspect-ratio保持旋转/CropBox后的比例；ResizeObserver只在实际宽度变化时失效，分辨率媒体查询处理跨屏DPR变化，同一宽度/DPR不重复渲染。保留附近150px按需加载、已完成Canvas复用、离屏清空、generation丢弃过期结果、RenderTask取消及临时Canvas释放；不增加全文缓存，不修改主PdfPage、缩放或文本选择。

新增tests/pdf-thumbnail.test.ts与e2e/reader-thumbnails.spec.ts；reader-fixtures.ts仅增加可选真实标题/正文/棋盘图样本，playwright.reader.config.ts纳入新用例。类型检查/生产构建通过、Vitest35/35通过，验证DPR1→2→3上限、相同尺寸复用、尺寸变化取消、离屏与卸载取消。生产Chromium真实PDF验证DPR1/DPR2、40页按需加载、当前页高亮/点击20页跳转、离屏释放/返回重绘、面板调宽缓存、导航切换及文献替换；另原A2六项回归全部通过，覆盖主阅读区缩放/选区、大纲、搜索、进度保存/恢复/冲突/失败草稿。

实测128×165.640625 CSS px：DPR1 backing store为128×166，DPR2为256×332；旋转页按CropBox比例显示。已查看普通与高DPI截图中的标题/正文及棋盘图边缘（小字号仍受固定128px视觉尺寸限制）。截图为忽略目录frontend/test-results/thumbnail-dpr1.png、thumbnail-dpr2.png。自动测试使用隔离临时SQLite/API和生产前端，未连接业务库；本次不修改后端、数据库或OpenSpec任务勾选，不运行Docker/commit/push。

手动验收沿用上方CMD仅重建nginx，Ctrl+F5后在普通/高DPI屏幕打开含标题、正文、图片的PDF，观察缩略图清晰度与原尺寸；滚动远页并返回，点击跳页、检查高亮、开关导航及切换文献。可在开发者工具检查Canvas像素宽度为显示宽度×min(DPR,2)。完成后等待用户验收，不进入P3-B1。
