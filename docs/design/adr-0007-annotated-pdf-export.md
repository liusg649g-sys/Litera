# ADR 0007：带批注PDF采用内容叠加与原生注释正文

日期：2026-10-17。状态：已采纳；P3-C1已获用户验收，Chrome/Edge显示正常由用户确认；Adobe未测试，版本号未提供。

## 用户反馈后的修订（2026-10-17）

用户要求取消末尾附录，并提供注释悬浮/点击查看。当前采用受限混合方案：
Text注释拥有确定的气泡AP、完整Unicode Contents和Popup双向关联；其余12类保持内容叠加。
自由文本/水印附加FreeText（自由文本及水印）正文语义层及Popup，空AP避免重复绘制，不改变原层叠。
2026-10-17原生Edge回归发现Stamp即使空AP仍出现额外评论图标，因此水印也使用FreeText；
保留全文及Popup。修复与旧版探针对比见`scripts/check_pdf_export_edge.py`及反馈修复记录。
导出页数严格等于原件；不再添加附录或气泡编号。Litera中提供悬浮与单击固定两种方式，
各100ms淡入/淡出；第三方弹出方式/动画由阅读器决定。API、资源隔离、快照和数据模型不变。
验证及人工步骤见[反馈修复记录](../development/p3-c1-comment-popup.md)。
以下是首轮5.1对比证据；其中“不采用混合”的初选已由本次用户决定取代。

## 首轮实验与决策（历史）

先运行 `backend\.venv\Scripts\python scripts\probe_pdf_export.py`，未接业务接口。
产物在 `.cache/c1-probe`。pypdf 6.20.1 + ReportLab 4.4.10 嵌入
Noto Sans SC（OFL，随代码分发字体和许可证），4 页 CropBox=[30,40,630,800]、
Rotate=0/90/180/270，13 类图元、中文/英文/αβ/±∞/箭头、透明 PNG。
MuPDF 1.26.7 独立渲染并目视检查首张全类型页面，嵌入字体可显示/提取中文，
源 SHA-256 不变；0.469 秒，Windows 进程 peak working set 104.4 MiB，产物 63792 字节。
这是小样本测量，不能外推大文件性能或 Edge/Acrobat 通过。

| 候选 | 实测与取舍 |
| --- | --- |
| pypdf + 页面内容叠加 | 保留原页面字典/Rotate/CropBox；新增矢量内容、嵌入字体和透明图像。13 类小样本均渲染可见；采用 |
| PyMuPDF | 原生 FreeText 的默认字体实验中提取中文为替换字符；MuPDF 显示有所替代，不能据此保证其他阅读器。API 有能力定制外观，但引入 AGPL/商业许可选择；仅隔离开发验证使用，不进运行依赖 |
| 标准 Annotation | 原生 Text 图标可见，正文仅在弹出面板，默认页面看不到；FreeText 需可靠 AP/嵌入字体；不能统一承诺13类原生编辑 |
| 直接 bake/扁平化 Annotation | Text 图标正文未转为页面文字，实验中丢失可见正文；不能单独采用 |
| 混合（内容 + 标准 Annotation） | 可增加原生编辑能力，但双重外观/打印/层叠复杂；本阶段无必要，不采用 |

首轮输出采用 **Litera 对象的矢量/文字/图像内容叠加**，保留原 PDF 自带批注。
注释画定位图标及编号，附加可见的全文批注附录；自由文本按框排版，超框内容和
水印正文也在附录完整保留。附录页追加，不改原有页面编号与尺寸。
不提供新增 Litera 对象在第三方的原生可编辑承诺。

坐标按 CropBox 左上归一化反算用户空间，叠加时仅平移 CropBox 偏移，
保留页面原 Rotate；字号/线宽除 UserUnit；图片保持比例并保留 alpha。
字体统一采用嵌入 Noto Sans SC 常规体，现有模型没有 fontFamily；对缺字明确失败，
不静默输出方框。不支持的字符可修改正文后重试。

## 接口与资源冻结

选择同步 `POST /api/v1/documents/{id}/annotated-pdf`，JSON
`{expectedAnnotationRevision: integer}`，成功直接返回 application/pdf 附件。
同一受保护请求同时完成创建与下载，无公开产物 URL、无数据库迁移。
快照时沿用文献写锁与集合 CAS，将源文件和所引用图片复制进独立私有工作目录，
拷贝完成即释放锁；这些副本是导出期间的资产租约，不延长原资产删除期限，
原件/原资产删除与后续编辑不能影响副本，也不阻塞原清理链。

每 API 进程并发 1；子进程隔离，60 秒、RSS 512 MiB、产物 200 MiB；
源50 MiB/资产合计50 MiB/快照JSON16 MiB/1000页/10000对象上限。
API 轮询进程、内存和连接；取消/断线/超时终止子进程，响应流最终关闭清理目录。
子进程父进程消失或超过期限自行退出；启动与周期扫描清理不活动的临时目录，
最迟1小时回收。子进程崩溃、错误或重试不修改业务数据。
下载阶段另限120秒。流开始前重新校验会话、owner、有效文献（含purge状态）；已发送字节不能撤回。

依据：[pypdf叠加](https://pypdf.readthedocs.io/en/stable/user/add-watermark.html)、
[ReportLab字体](https://docs.reportlab.com/reportlab/userguide/ch3_fonts/)、
[PyMuPDF许可](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)。
最终逐类矩阵及后续正式实现测试见 [C1记录](../development/p3-c1.md)。
