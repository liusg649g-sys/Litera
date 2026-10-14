# 规划校验记录

校验日：2026-10-14，OpenSpec CLI 1.14.1，schema=spec-driven，repo-local root=`D:\PKU\Projects\reacher-hub`。

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
