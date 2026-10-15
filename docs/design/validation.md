# 初始总体规划校验记录

初始校验日：2026-10-14，OpenSpec CLI 1.14.1，schema=spec-driven，repo-local root=`D:\PKU\Projects\Litera`。

本文下文保留初始规划时的计数与环境历史，不是当前开发状态。01现已通过用户功能/UI验收，最新开发与测试记录见[交接](../../HANDOFF.md)。

## 2026-10-15 P3-A1交互补充验证（最新）

- 仅A1补充，仍6/36；跨01/02 UI修改涵盖共享标签、标题阅读/详情/下载、折叠导航Tooltip、阅读组、紧凑图标、左面板拖动及渲染反馈；没有启动A2或批注业务。
- 用户本轮授权首个真实页面完成后调用现有PUT progress {}；服务器lastReadAt保持原实现。真实浏览器验证一次记录、最近阅读展示、失败诊断/显式重试，下载/详情/失败渲染不写记录；完整页码/缩放持久化仍未实现。
- vue-tsc/Vite生产构建通过、Vitest26/26；生产阅读器Chromium12/12、文献库完整浏览器22/22、后端pytest73/73。真实HTTP/PDF，隔离临时SQLite，未做本轮MySQL专项验证。故障注入预期日志及一次连接重置后的完整重跑见[交互记录](../development/p3-a1-ux.md)。
- OpenSpec严格校验6/6、issues=[]，git diff --check通过。未运行Docker、迁移/重建用户数据、commit/push/sync/archive。等待用户手动重建前端并实际验收。

## 2026-10-15 P3-A1实现验证（历史）

- 仅02任务1.1–1.6完成，6/36；A2及后续30项未开始，用户实际体验待验收。实现/版本/命令/证据见[P3-A1记录](../development/p3-a1.md)。
- pdfjs-dist精确6.4.299，真实同版module Worker与本地CMap/字体/WASM/ICC生产资源；vue-tsc/Vite构建通过、Vitest26/26。
- 生产Chromium真实API reader7/7，另加公开真实学术PDF1/1，覆盖复制/三视图/导航/下载、窄屏、跨文献取消释放、401/404/416/网络/实际私有文件损坏恢复、DPR2旋转CropBox。40页样本仅属必要资源验证，不是完整性能验收。
- Change 01完整真实HTTP文献库浏览器22/22，后端pytest73/73；均临时SQLite/私有PDF目录，不是MySQL集成验收，保留历史弃用/颜色变量及预期故障注入日志。
- `openspec validate --all --strict --json`：6 passed、0 failed、issues=[]；git diff --check通过，未跳过规格/未同步归档。结构校验不代替业务测试。
- 没有运行Docker Compose或修改开发数据库/用户/PDF数据，没有业务迁移、commit/push、03–06实现；既有参考图和未提交文档改动保留。下文全部为此前历史记录，不改写原证据。

## 2026-10-15 Change 02规约重审（最新结果）

- 范围：只改02 proposal/design/两个spec/tasks及必要公共文档/交接；逐张读取15–25及索引，核对现有路由、阅读入口、pypdf、Cookie/Origin/CSRF、content/Range、progress与清理代码。
- 02现为20条Requirement、49个Scenario、36项实现任务全部未勾选（0/36）；A1→A2→B1→B2→C1→C2，每阶段有独立交付物、测试和用户验收门槛。下文旧0/12等计数为历史，不代表最新计划。
- 使用本机已安装OpenSpec 1.14.1；PATH未含CLI，改用现有绝对路径。只读list/status/instructions确认repo-local root、4/4规划产物；没有安装依赖或修改schema。
- 本轮`openspec validate --all --strict --json`：6 passed、0 failed，所有issues=[]；02有效。严格校验仅证明规约结构，不证明阅读器已实现。
- 本轮Markdown检查范围为HANDOFF、根README、change总览、docs/design及02全部文档：17文件、本地链接87个、缺失0。git diff --check通过，仅Git LF/CRLF转换提示。
- 已移除旧AI浮球/业务工作区、书签、两组视图自由组合及旧12项任务；写入三视图/50%–500%、14类对象/资产、集合CAS/幂等收据/补偿撤销、进度兼容、导出快照/第三方可见矩阵及资源预算。
- 已查阅PDF.js、pypdf、PyMuPDF官方文档，来源链接在02设计；导出具体方案留C1验证后决策，没有提前安装或声称全类型可编辑。
- 未改frontend/backend业务、锁文件、迁移、01/03–06产物或历史测试文件；未运行业务测试、数据库迁移、Docker Compose，未commit/push/sync/archive，未启动任何P3阶段。原有未跟踪参考图/索引保留。
- 下文全部为此前规划/收尾证据，不覆盖、不改写其测试结论；01专项MySQL补证仍按原交接跟踪。

## 2026-10-15 前次收尾核对（历史）

- 范围仅文档与02关键依赖：会话/CSRF、文献与PDF内容/Range、打开记录、路由/公共组件，以及必要迁移/Compose配置接入信息；没有全面代码审查。
- 01为33/34：用户功能/UI验收已确认，5.B1保留用户勾选，5.A1只剩专项MySQL日志补证；02–06实现任务保持0/12、0/6、0/6、0/7、0/8。
- 主规格仍为空，未执行sync或archive；功能验收条件已满足，完整任务追踪仍待5.A1补证。
- 本次执行OpenSpec 1.14.1的 `openspec validate --all --strict`：6 passed、0 failed；最终Markdown检查24个文件、86个本地链接，缺失0。HANDOFF为134行，git diff --check通过（仅换行转换提示）；不把结构校验当作业务测试。
- 初次沙箱校验因目录realpath EPERM失败；同一只读命令在获准本机权限下重新执行通过，没有修改规约格式绕过检查。
- 没有重跑前后端业务测试、Docker/MySQL或浏览器验收；历史证据与用户验收分开记录，02依赖缺口见其design。

## 官方校验

`openspec validate --all --strict --json`：6 个 change 全部 valid=true，issues=[]；passed=6、failed=0。每个 `openspec status --change <name>` 显示 4/4 artifacts complete：proposal、specs、design、tasks。未跳过任何产物，未使用skip_specs，未同步/归档主规格。

| Change | Spec文件 | Requirement | Scenario | 未开始任务 | 已完成实现任务 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01-literature-management | 2 | 14 | 31 | 20 | 0 |
| 02-pdf-reader | 2 | 9 | 20 | 12 | 0 |
| 03-translation | 1 | 4 | 9 | 6 | 0 |
| 04-literature-notes | 1 | 5 | 8 | 6 | 0 |
| 05-metadata-extraction | 1 | 6 | 12 | 7 | 0 |
| 06-ai-qa | 1 | 6 | 12 | 8 | 0 |
| 合计 | 8 | 44 | 92 | 59 | 0 |

artifact 的 done/[x] 是CLI对文档存在性的标记，不是tasks checkbox或模块开发进度。本批59项实现/验证任务均保持`- [ ]`，03–06明确待实现。

## 人工与结构核对

- 已读取需求全文与五张截图，截图分析逐张列于ui-guidelines。
- 能力与proposal路径对应，无现有主规格冲突；文献库导航伸缩归01/P2，阅读器布局归02/P3。
- 正常/异常/权限场景覆盖六模块；各模块task附验收方式，测试与文档放在所属任务组。
- 公共契约统一camelCase、string ID、UTC时间、物理1-based页码、归一化选区、owner过滤、提取/索引版本与标准错误。
- P1仅任务1.x、P2后续组、P3独立02；未就绪模块不出现假功能。
- 公共文档与change Markdown本地链接检查无失效目标；本记录写入后复核。
- frontend/backend/scripts/storage仍无文件；没有业务代码、业务表DDL、依赖安装、容器启动或Git提交。

## 本机环境说明与限制

初次sandbox内`openspec new change`报“Schema 'spec-driven' not found”，而schemas能列出标准schema。正常本机权限下命令成功；诊断期间的本地schema副本已移除，最终仍使用原装标准schema且config.yaml未修改。这属于本次工具运行环境，不是业务实现或OpenSpec格式缺陷。

OpenSpec校验不验证UI视觉、API可运行、SQL迁移正确或真实模型质量，本次也未运行任何业务测试。表中场景是未来验收条件。没有另附原始课程选题书，需求全文是本批范围依据；另有文件需补充比对。重要建议D1–D7及后续配置Q1–Q7见decisions.md，实施前按阶段评审。

## P3-A2最终验证（2026-10-15）

- 02仅完成tasks 2.1–2.6，总体12/36；A1用户已验收，A2用户体验待验收，B/C及03–06未实施。
- vue-tsc/生产构建通过；Vitest34/34；隔离SQLite后端pytest91/91，含0003→0004保留旧记录与MySQL离线增量DDL编译。未运行真实MySQL/实际业务库迁移或Docker。
- 真实PDF生产Chromium按套件19项通过（A2 6、A1交互5、A1基础8）；文献库22项通过（12+10）。测试进程中断、worker启动异常及首轮实际失败均未计通过；修复与重跑范围见[P3-A2记录](../development/p3-a2.md)。
- OpenSpec 1.14.1全部严格6/6、issues=[]；17份当前文档/96条本地文件链接缺失0，git diff --check通过。未sync/archive/commit/push，交付后停止。

## P3-A2 UI/UX补充验证（2026-10-15）

本轮仅前端紧凑栏高/共享字号、SVG箭头、局部焦点、12px间距/fit及PDF.js全局.spread margin冲突修复；后端/业务数据库未改，仍12/36，不新增阶段或任务。用户已在Docker体验A2核心，本轮UI待手动验收。

- vue-tsc/生产构建及Vitest34/34通过；生产真实PDF阅读器22项分组通过（布局+A2 9、原UI 5、基础8）；文献库22项通过（12+10）。后端未改且未重跑，未执行MySQL集成或实际业务库迁移，不把历史SQLite结果当本轮MySQL证据。
- 严格校验6/6、issues=[]；本轮10份相关Markdown/60条本地文件链接缺失0，git diff --check通过。测量及CMD步骤见[UI记录](../development/p3-a2-ux.md)。
- 1366×768阅读区实测640px，fit-height页面616px、上下各12px；双页fit-width原1373/1366的7px溢出来自PDF.js全局.spread margin-inline:3.5px，局部清零后可完整容纳时无横向溢出，500%真实超宽可滚动。
- 未运行Compose、commit/push/sync/archive，完成后停止待用户验收，不进入B1。
