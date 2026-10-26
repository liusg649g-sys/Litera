> 2026-10-26状态更新：用户已确认统一5183五项人工验收全部通过，翻译与笔记开发验收完成。本文后续“等待验收/停机”等是对应历史时点；当前GitHub提交前准备、Linux兼容补丁和测试边界见docs/delivery/github-delivery.md，不能把历史状态当当前运行结论。

# 用户自定义 AI 模型设置第一版开发与验证

> **最终状态更新（2026-10-26T18:56:47+08:00）**：代码/测试完成，但新预览在最后一次启动后触发原10GB保护并正常关闭，**当前不能访问**。D盘曾18,060,488,704字节，检查时下降至9997811712字节；C盘15509032960字节。API日志Application shutdown complete、PID清单已清理，新旧数据库完整性通过。不得用下文早先启动时的200声称当前运行；没有降低阈值或再次重启。等待用户释放空间或审核低资源启动方案，OpenSpec部署交接任务保持未完成。


记录：2026-10-26T18:40:23+08:00；分支local/litera-dev-20261020；HEAD947dc3cc6381ce4b19d587762950f381b6e31100。本轮为本地未提交增量，不是GitHub已发布功能。

## 已实施

- /settings/ai：从个人资料进入；本人的服务类型/BaseURL/模型/密码型Key输入，保存、修改、清除Key、确认删除、显式测试和状态。空Key保留原值，成功后清空输入；不写浏览器存储，不回显已保存Key。
- 后端user_models.py复用认证/CSRF、DPAPI vault和统一模型服务。随机revision CAS、明确user/developer选择及迟到结果保护；沿用译文来源、笔记保存、乱码保护与实时500ms逻辑。
- 新隔离站127.0.0.3:5183/API8004，独立SQLite/PDF/会话/TMP；可注册自己的新账号。无自动注册、预置模型或真实Key，开发者配置读取被禁用，页面清楚标记隔离。
- 原有developer配置和5180 Mock代码仍保留。未来QA可复用配置/ModelProfile/ModelService，但未实现QA。

详细数据结构、API及安全限制见[设计](../design/user-model-settings.md)；OpenSpec为07-user-model-settings。

## 实际自动化

| 检查 | 通过 | 失败 | 跳过 | 环境 |
| --- | ---: | ---: | ---: | --- |
| 后端最终15套件 | 340 | 0 | 0 | 临时SQLite、HTTP Mock；另真实Windows DPAPI本地密码学测试 |
| 新启动器退出守护 | 2 | 0 | 0 | 受控Server替身，不停止真实进程 |
| 前端29文件 | 211 | 0 | 0 | Vitest/happy-dom、Mock |
| 新用户模型浏览器 | 3 | 0 | 0 | 临时SQLite、HTTP Mock、实际PDF.js |
| 旧笔记浏览器 | 12 | 0 | 0 | 临时SQLite、Mock |
| 旧翻译浏览器 | 11 | 0 | 1 | 私人PDF opt-in跳过 |
| 摘录/搜索/导航/B1/D1/生命周期浏览器 | 17 | 0 | 1 | 临时SQLite/合成PDF/Mock；私人PDF opt-in跳过 |
| vue-tsc / npm run build | 通过 | 0 | 0 | 复用已安装依赖，未装新包 |
| 真实模型、真实MySQL、真实QA | 未执行 | — | — | 我执行的真实请求0；用户手动验收待进行 |

总计596自动化通过、2跳过，重复运行不累计。后端/浏览器日志及JUnit在.cache/user-model-work；前端测试和构建结果来自本轮命令输出，未另存完整前端日志。原批注回归33项包含于后端340。无生产MySQL验收结论。

初轮如实记录：旧模型输出截断单测因Mock factory重复transport参数1失败/89通过，修测试替身后恢复，不改断言；前端confirm缺失1失败/210通过，补原生确认替身后211通过；完整后端先306通过/1失败（旧迁移断言固定0007），更新真实head预期并补批注迁移后340通过。自动权限审查有一次只读调用超时，按工具提示重试成功，没有被阻止的剩余操作。测试保留Starlette/httpx弃用警告；生产构建保留大chunk提示，不当成失败或顺手重构。

关键命令：

```powershell
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_backend.py final-backend-v2 <报告JUnit记录的15个test文件>
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run build
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_browser.py user-models
.\backend\.venv\Scripts\python.exe .cache/user-model-work/run_browser.py notes translation captures
openspec validate 07-user-model-settings --strict --no-interactive
.\scripts\user-model-preview.ps1 start
.\scripts\user-model-preview.ps1 status
```

驱动在无.env临时cwd运行；后端禁非loopback网络、清空继承AI_/TRANSLATION_变量、临时PDF/TMP及每2秒10GB守护。浏览器固定5184/8006或已有临时测试端口，不连接5177/5180。仅测试fixture替换HTTPtransport；实际用户预览没有Mock替换。

## 实际部署与完整性

首次启动成功，随后仅为增强新站Windows双层Python退出守护进行两次有备份、空数据库前提下的停止/启动验证：.cache/user-model-preview，0008；首页、5183代理健康、8004健康均HTTP200。实际Chromium打开/login：200、正确独立预览横幅、pageerror=0，截图.cache/user-model-work/preview-login.png。匿名/auth/session为预期401（首次诊断urllib未捕获HTTPError打印回溯，不是服务故障）。没有创建实际预览账号/文献或触发模型测试。

迁移前备份：`D:\研究生\课程\互联网软件开发技术与实践\作业\小组作业\Litera-backups\user-model-preview-before-0008-20261026-183248`；3文件247226字节，逐路径/大小/SHA256一致。备份库及复制恢复库integrity=ok/FK=0，空基线用户/文献/笔记/关联均0，恢复验证副本保留在新数据目录，不覆盖原库。

旧5180：1账号/3文献及PDF/7笔记/12关联/6来源块，7表行指纹及3PDF SHA256全部前后相同，integrity=ok/FK=0，仍0007。旧D1备份目录仍保留；它早于部分人工新增数据，不声称可恢复当前全部数据。5177、5180本轮开始已不响应，未启动或修改数据。新站验收不依赖旧站恢复。

部署后磁盘字节：C=15649386496，D=18062585856，均高于10,000,000,000字节。新启动器与原启动器均保留原阈值，无Windows设置改动。

## 人工验收（待用户执行）

1. 打开http://127.0.0.3:5183，确认黄色“用户模型独立预览”横幅，自行注册并登录新的隔离账号。
2. 个人资料→AI模型设置，填写公网HTTPS BaseURL、模型名、自己的Key。可自行输入候选 https://ai-gateway.devops.hello1023.com/v1 / course-chat；本轮没有验证它们可用。不要在聊天发送Key。
3. 保存设置：应提示尚未验证，Key输入清空。主动测试连接：成功后标记已验证；错误Key/不存在模型/超时/额度/SSRF显示脱敏错误，不自动重试或调用开发者Key。
4. 上传新目录中的public-translation-test.pdf（普通公开合成句子，约1.4KB），打开阅读器与翻译栏，在“翻译模型”**明确选择我的模型**，选区手动翻译。检查实际译文、方向、原文及页码。每次重新打开阅读器都请核对选择项，当前不持久化模型选择偏好。
5. 保存译文到新/已有笔记，确认真实结果显示model_api而不是隔离Mock标签，刷新验证来源和内容。实时模式继续500ms防抖；本轮未另开发实时机制。
6. 设置更改地址/模型/Key后，应重新测试；清除Key和删除设置后不能用个人模型继续翻译。原有已保存笔记不应变化。

启动/停止只用user-model-preview.ps1 start/status/stop，不用notes-preview或local-site。新站后台常驻，浏览器关闭不停止；低于10GB会正常停止，不降低阈值。

## 当前限制与停止点

仅单用户一个OpenAI Compatible配置、公网HTTPS443、Windows DPAPI；不支持内网或其他协议、跨机器密钥迁移、持久化模型选择偏好。连接通过不等于翻译质量通过。旧启动器对0008head会主动拒绝，本轮未改guard或恢复旧环境。用户真实模型和新UI人工验收待确认；P3-E2/P3-D2、MySQL、QA、旋转/OCR均未开展。

最终新启动器附加验证：Windows进程树含venv启动器及实际API，因此增加实际uvicorn worker的stop.request/10GB主动退出与所属进程树兜底。原版本本次停止也未遗留进程，不将“可能遗留”冒充已复现故障。新版本实际停止：日志Application shutdown complete、所有所属PID退出、5183/8004均释放、SQLite完整性通过，再启动保持服务可访问。两项新增单测仅用Server替身；不重复累计先前340项。实际停止证据.cache/user-model-work/launcher-lifecycle.json；空库0008额外备份before-launcher-fix.db已验证，无覆盖原备份。

### 最后存储保护中止（实际运行）

第三次启动曾健康200，随后监督日志明确below 10 GB，API正常shutdown，最终首页/代理健康/8004均拒绝连接。未再次启动。上述三处产物大小（仅本轮工作目录、预览数据、frontend/dist）：477593、505918、6528467字节，合计约7.5MB，不能解释约8.06GB突降；没有调查系统分页文件或其他私人目录，根因本轮未确认，不能断言就是分页文件或Litera文件增长。

业务实现及Mock测试完成不等于当前网站可人工验收。若需优化，可在用户确认后评估用已构建静态产物与同源代理替代Vite，减少开发服务器开销；该方案未实施、降低多少内存未测量，不修改Windows设置或10GB阈值。先等待用户处理空间，不继续开发QA等其他阶段。
