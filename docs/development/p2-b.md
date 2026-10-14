# P2-B 文献管理交付记录

收尾更新（2026-10-15）：用户已确认Change 01实际功能/UI验收通过；以下保留开发当时的测试/部署记录，旧“待验收”描述不代表当前用户状态。专项MySQL日志未在本次提供，最新状态见[HANDOFF](../../HANDOFF.md)。

日期：2026-10-14。用户已明确启动01的P2-B；保留P1、P2-A及已验收布局。本轮未运行Docker、未Git commit/push、未删除真实数据库/PDF/用户数据，不进入02。

## 实际功能与实现入口

- backend/migrations/versions/0003_library.py、app/models.py：五个个人库表及documents三个nullable字段，增量升级保留ID/题录/文件键；MySQL最近打开时间DATETIME(6)。
- backend/app/library.py：文件夹/标签CRUD、嵌套归属与名称唯一检查、分类解除保留文献；组合搜索/全部标签匹配/年份/排序分页；progress已打开子集与真实最近阅读；回收站恢复及持久化清理作业。
- backend/app/documents.py：上传可带本人folderId，同一PATCH/version保存题录及folderId/tagIds；DTO返回真实分类/lastReadAt及nullable cleanupJob，原PDF/Range/重复检测保持。
- frontend/src/views/LibraryPage.vue、library.ts、components/DocumentInfoPanel.vue：原布局上接入五个导航、个人文件夹、标签管理、筛选和生命周期；分类编辑复用面板表单和局部未保存确认。阅读打开空窗口后调用真实progress API，再导航浏览器PDF；下载不记历史。浏览器拦截弹窗会提示允许后重试。
- components/LibraryActionDialog.vue、library.css：主题一致的局部尺寸确认/命名弹窗（420px、视口减32px），窄屏保持边距；回收站固定右侧操作并内部横向滚动。参考06–13，未复制商业、自动过期、一键清空或多级目录。

新增兼容契约仅属于01：POST /cleanup-jobs/{jobId}/retry；DocumentDTO.cleanupJob可空；reading-history支持与列表相同筛选且固定最近时间倒序。02的progress仅实现已打开子集，非null页码/缩放明确503；未实现PDF.js、标注、翻译、笔记、提取或AI。

## 清理一致性

软删除保留全部数据和PDF，普通列表/内容/进度404，重复上传409且指向本人回收站。恢复原ID和关联；分类已被删除时归未分类/解除标签。

永久删除必须二次确认。先提交不可恢复标记与pending作业，再CAS领取running，持作业行写锁处理PDF及数据库关联；失败返回202/failed、保留作业及文献墓碑，UI不报成功。刷新回收站仍显示状态；GET查询与POST重试均检查owner，运行60秒租约到期后也可显式重试。已开始永久清理不能恢复。文件已删除但DB清理中断时，重试将缺失文件视为已清理并完成关联删除；完成仅保留作业审计，清空storage_key。

没有后台自动清空或上传孤儿文件扫描器。进程硬退出可能留下未引用的上传临时/发布文件，此既有边界不被本轮永久删除作业掩盖。未创建未来成员模块的关联或向量索引；后续模块须接入真实清理流程后才宣称清理其数据。

## 自动化证据

| 验证 | 本轮结果 | 范围 |
| --- | --- | --- |
| vue-tsc + Vite build | 通过 | 当前前端代码，未构建Docker |
| Vitest | 10/10 | 原请求/认证/布局单元回归 |
| 后端pytest | 73/73 | 临时SQLite真实迁移、API、文件；含P1/P2-A，权限、名称/分类、组合搜索、历史、生命周期、并发打开与清理重试、旧数据升级 |
| 文献库Playwright | 17/17 | 临时SQLite FastAPI + Vite +真实文件；12项P2-A回归及5项P2-B闭环 |
| 最终窄屏局部修复 | 3/3 | 回收站操作列覆盖普通表格宽度，按钮完整可见；真实阅读/恢复/永久删除及六列表格定向回归，重新构建通过 |
| auth-ui | 10/10 | 登录注册主题、校验及桌面/窄屏回归 |
| OpenSpec strict | 6/6 | 全部change严格校验；01当前29/31，剩余两项为用户部署验收 |

P2-B浏览器用例覆盖创建/改名/删除分类、文件夹内上传、分类保存与刷新、分类草稿继续编辑、23篇真实文献组合筛选/分页/空结果、实际PDF打开与历史、两用户隔离、软删除/恢复/永久删除、网络失败保持确认和重试、360px弹窗边界。

清理故障浏览器用例在测试服务专属临时目录中将本次上传PDF暂移并用同名空目录制造实际Windows文件系统拒绝删除；真实DELETE返回failed作业，刷新与查询保持失败，恢复测试文件后界面重试完成删除。成功数据/状态不模拟；另有网络错误注入仅用于验证失败UI。截图检查搜索表格与窄屏回收站确认，既有1920/1280/390/360及面板截图保留。

认证UI及OpenSpec最终结果见HANDOFF。Starlette/httpx弃用与Node颜色变量警告仍存在，不影响已通过测试。**本轮MySQL、Docker、已部署auth-integration未运行，不能用以上SQLite证据替代MySQL集成验收。**

## Windows CMD 自动化复现

```cmd
cd /d D:\PKU\Projects\Litera\backend
set TEST_DATABASE_URL=
.venv\Scripts\python -m pytest -q
cd /d D:\PKU\Projects\Litera\frontend
npm run build
npm test
npm run test:library
set LITERA_UI_PORT=5176
npm run test:e2e -- --project=auth-ui
cd /d D:\PKU\Projects\Litera
openspec validate --all --strict
```

需已安装backend/.venv依赖、frontend依赖和Chromium。浏览器测试自动启动临时8001 API和5175 Vite，结束正常清理；不要并行运行其他占用相同端口的测试服务。打开网页本身不会停止Vite。

## 用户手动部署及MySQL验收

已有.env与命名卷保留，无需重新初始化。升级前联合备份MySQL和PDF卷，不执行down -v，不删除或重建业务表。以下命令只供用户手动执行，代理没有运行：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
docker compose exec -T api python -m alembic current
docker compose exec -T api python -m pytest -q
cd frontend
npm run test:e2e -- --project=auth-integration
```

API启动自动迁移至0003_library。pytest仅允许独立litera_test；旧卷若没有该库，按scripts/mysql-init.sql检查/创建独立测试库并授权，不清理业务库。本轮新增行为测试会在所配置MySQL测试库执行；专门的旧版本升级样例仍使用临时SQLite，真实MySQL升级保留必须额外核对已有账号、文献ID与PDF。

1. 打开http://localhost:8080/login，用已有账号登录，确认原文献与PDF保留、内容URL的documentId不变。侧栏折叠/拖动、右侧面板调宽、52px栏与主题应保持。
2. 新建文件夹，在文件夹内导入PDF，刷新验证归属；更多→移动到文件夹修改归属并保存；改名，再删除文件夹，文献仍保留且归未分类。
3. 标签管理新建/重命名标签，在信息面板勾选多个标签、保存刷新；点击表格标签筛选；删除标签后文献和PDF保留。修改分类后尝试关闭/切换，继续编辑应保留，放弃才执行原操作。
4. 检索词+文件夹+多个标签+年份组合检索，切排序和分页；输入无匹配词检查空状态，清除恢复列表。两窗口旧版本保存应保留草稿并提示冲突。
5. 点击阅读，允许浏览器弹窗后查看真实PDF；最近阅读只出现打开过的文献，再打开更新时间；单纯刷新/下载不更新。阅读Tooltip可查看真实最近打开时间。
6. 移入回收站，普通列表/历史中消失且内容URL404；重复上传提示回收站并能跳转；恢复后题录/分类/PDF和ID保持。
7. 用一篇专门用于验收的文献确认永久删除，取消/Esc不删除；确认后无法再访问，同PDF可重新上传。不要用需要保留的真实文献测试永久删除。
8. 清理失败状态可依靠独立测试库pytest与临时浏览器故障用例验证；部署手动模拟故障应仅用专用验收文献/存储，恢复文件权限或占用后点击查看状态/重试，不能把202当成功。无需破坏真实PDF来验收。
9. 第二账号确认文件夹/标签/文献/历史/回收站均隔离，复制另一账号分类ID、文献URL、作业ID的读写均404；检查会话退出后401回登录。
10. 缩至390/360px，文件夹/标签命名和永久确认不超宽；表格只内部滚动，抽屉分类保存、局部草稿确认可用。

OpenSpec的5.A1和5.B1保留待用户部署验收。完成后停止，不同步/归档整个change，不自动进入02。
