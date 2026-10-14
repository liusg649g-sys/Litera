# P2-A 文献库交付与验收

日期：2026-10-14。Change：01-literature-management。本轮只实施P2-A，完成后停止待用户实际验收，P2-B未启动。

本文保留P2-A首次业务交付证据。后续纯前端优化已将详情弹窗改为右侧面板、精简为六列表格并调整菜单/通知，最新UI与11项浏览器回归见[p2-a-ui.md](p2-a-ui.md)；API/数据/部署限制不变。

## 已实现

- 本地PDF上传：默认50 MiB，配置MAX_UPLOAD_BYTES；GET /api/v1/library/config返回真实上限。签名与结构校验、拒绝加密/损坏/零页文件、私有路径、原子发布、失败回滚/补偿。
- 同用户SHA-256唯一约束（含deletedAt记录）、并发重复409；不同用户相同PDF正常独立创建，不泄漏其他用户文献。
- 本人文献列表/分页/基础排序，详情读取与手工题录CAS编辑，浏览器真实预览/下载，单Range 206/416；写入Origin/CSRF及逐次owner检查。
- 新增0002_documents迁移只创建documents/document_files，保留P1账号。PDF命名卷只挂载API；Nginx不提供私有静态路径。
- 品牌栏/导航/导入/表格/分页/详情，默认导航240px、180–320px拖动或键盘调宽、56px折叠；窄屏覆盖导航、表格内部横向滚动，操作列固定右侧。使用现有#9B0000 Token。
- 稳定documentId；/reader/:documentId返回原文献详情并说明阅读器待实现。parseStatus=not_requested，pageCount/extractionVersion=null，不提取正文或题录。

文件夹、标签、组合检索、最近阅读、回收站/永久清理属于P2-B，只显示明确待实现入口，不发起业务请求。DTO中folderId=null、tags=[]、lastReadAt=null反映该阶段未设置状态。DocumentUploadedV1只定义契约，尚未派发/入队。

## 自动化证据

| 检查 | 本轮结果 | 边界 |
| --- | --- | --- |
| 前端 build | 通过 | vue-tsc + Vite，未构建Docker镜像 |
| Vitest | 10/10 | 请求封装、multipart/错误details、布局边界与既有校验 |
| pytest | 63/63 | 临时SQLite、真实迁移、外键、HTTP、文件系统；含P1回归 |
| Playwright 文献库 | 6/6 | 临时SQLite FastAPI + Vite；真实Cookie/API/落盘，无模拟成功数据 |
| Playwright auth-ui | 10/10 | 既有认证UI隔离回归，使用5176避免已占用5174 |

后端覆盖合法上传/伪PDF/加密/文件与请求流大小边界、私有路径、磁盘/DB错误补偿、提交确认丢失时保留已提交文件、并发重复、跨用户隔离、CAS并发、null/省略字段语义、Range/极端Range、升级保留P1用户。SQLite结果不替代MySQL约束验收。

文献库浏览器覆盖上传→编辑→刷新持久化、PDF原字节、浏览器下载文件名、重复详情、两用户隔离、21条真实数据分页排序、拖动/键盘/折叠恢复、窄屏、真实无效文件与版本冲突保留草稿、加载/网络失败重试、待实现入口不请求服务、真实退出后401回登录。截图检查1280×720、1920×1080、390×844、360×560，页面无整体横向溢出。测试PDF由代码生成，无敏感文献。

pytest仍有Starlette/httpx弃用警告；不影响通过。未运行MySQL/容器及最新部署的auth-integration，不将历史结果计为本轮验收。OpenSpec校验结果见HANDOFF。

复现命令（Windows CMD）：

```cmd
cd /d D:\PKU\Projects\Litera\backend
.venv\Scripts\python -m pip install -r requirements.txt
set TEST_DATABASE_URL=
.venv\Scripts\python -m pytest -q
cd /d D:\PKU\Projects\Litera\frontend
npm ci
npm run build
npm test
npm run test:library
set LITERA_UI_PORT=5176
npm run test:e2e -- --project=auth-ui
```

首次浏览器环境需要`npx playwright install chromium`。test:library自动启动8001 API和5175 Vite，临时目录存SQLite/PDF，正常退出清理，禁止替换为开发库。两个Playwright配置使用不同输出目录，避免相互清理截图。

## 用户手动部署与实际验收

以下Docker命令仅供用户手动执行，本轮代理未运行任何Docker命令。

1. 已有.env无需重新生成秘密；可追加MAX_UPLOAD_BYTES=52428800及PDF_STORAGE_ROOT=/data/pdfs（不追加时Compose也采用这两个默认值）。备份现有MySQL数据，新PDF卷与数据库以后应联合备份。
2. 在CMD执行：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose up -d --build --wait
```

3. 打开http://localhost:8080/login，用原账号登录，确认账号保留，进入“我的文献”。检查默认240px侧栏、收起/展开、拖动限宽及窗口缩小后可操作。
4. 导入一份未加密PDF：列表显示文件名题名、附件大小，刷新后仍存在。再导入同字节文件，应提示重复且可查看已有文献，不新增第二条。
5. 点击详情/编辑，修改标题、作者（每行一位）、年份、期刊、DOI、摘要、关键词，保存并刷新核对。两个窗口编辑同一文献，旧版本提交应提示冲突并保留草稿。
6. 点击预览与下载：浏览器应打开真实PDF，下载原文件名，内容与原件一致；题录编辑不修改PDF。记录内容URL中的documentId，刷新/编辑后不变；访问/reader/该ID时显示详情及待实现说明。
7. 用第二账号确认第一账号文献不出现在列表，复制第一账号详情/内容URL请求应404；相同PDF在第二账号可独立导入。
8. 选择伪PDF和超过50 MiB文件，确认错误且列表不增加；缩至390/360px，表格仅内部滚动，详情表单可操作。确认分类/检索/最近阅读/回收站明确待实现。
9. 可停止并重新启动现有服务（保留卷），确认PDF仍可访问。不要使用down -v。
10. 独立测试数据库验收：

```cmd
cd /d D:\PKU\Projects\Litera
docker compose exec -T api python -m pytest -q
cd frontend
npm run test:e2e -- --project=auth-integration
```

pytest强制MySQL测试库名为litera_test，拒绝清理非测试库；若已有旧MySQL卷未创建测试库，先按scripts/mysql-init.sql检查/建立独立测试库，不改写开发数据。此步骤待用户执行并反馈，不勾选5.A1。

## 实现与部署限制

文件系统和数据库无统一事务，正常异常有补偿，但进程硬退出仍可能留下未引用临时/发布文件，P2-A不具备崩溃恢复清理作业。提交确认丢失返回失败而保留已提交PDF，刷新列表或重新上传可确认是否已成功。PDF卷必须持久化，不能将私有目录映射为Nginx静态路径。生产HTTPS、跨进程限流与其他模块保持既有阶段边界。

本机非容器运行API时，PDF_STORAGE_ROOT须设置为项目内可写目录，例如D:\PKU\Projects\Litera\storage\pdfs；Compose使用容器路径/data/pdfs。导航宽度本页内存保留，刷新回默认，未新增浏览器凭证或PDF文本存储。

P2-A用户验收通过后，等待单独P2-B指令；不自动进入P2-B或02–06，不归档整个01，不commit/push。
