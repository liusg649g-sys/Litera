# 2-后端开发规范

> 跨仓适用说明：规范约束两仓后续开发，本文实现快照来自Litera-test。原Litera目前仅01/02、迁移至0006；03/04/07及0007/0008尚未合并，相关“现有”描述只属于Litera-test，在原项目按待接入要求理解。文件同步不等于代码、脚本或部署已合并，先查本仓实际文件；总表见[规范索引](README.md)。

适用：`backend/`、API契约、服务端配置和迁移。常驻入口：[AGENTS.md](../../AGENTS.md)；授权细节归 [安全规范](3-security.md)，部署执行顺序归运维负责人。

## 当前分层与课堂示例的适配

当前为FastAPI按能力组织的平铺模块，不是Go样例的`internal/db`，也没有独立repository目录：

```text
main.py                         配置、会话、异常与路由装配（历史认证逻辑也在此）
schemas.py / 各模块InputModel    请求边界与类型校验
documents/library/annotations/  业务路由、owner查询、事务（既有合并层）
notes/note_captures/user_models  同上；不得声称已完全分离
model_service/ai_service        模型业务门面、适配器
model_network/model_secrets     外部网络与安全Vault适配器
database.py / models.py         引擎、会话与ORM；SQL也存在于能力模块
migrations/versions             Alembic结构演进
```

**既有例外**：保留路由/业务/SQL同模块及少量跨能力共享helper；不为符合课堂层名重构。增量新模块在自身能力内区分“请求校验→业务编排→数据访问helper”，外部服务经适配器；数据库查询集中到该能力数据访问函数，避免新增编排函数直接散写SQL。涉及历史公共helper需列生产者/消费者，不能再制造反向依赖。未来真正拆层须独立change和兼容验证。

## 十二项约束

| ID / 课件条目 | 具体约束 | 检查/验证方式与依据 |
| --- | --- | --- |
| B01 分层/依赖方向 | 新能力沿用上方边界，业务编排调用数据访问helper和适配器；适配器不导入main.py/前端；不得循环依赖 | 逐个检查新增import和SQL所在函数；给“模型适配器反向import main”的片段应指出违规。既有合并层按例外处理 |
| B02 命名/版本 | 公共API前缀`/api/v1`，普通资源小写复数，GET读/POST创建或明确动作/PATCH局部/DELETE删除；DTO camelCase，Python/DB snake_case | 核对OpenAPI、router和frontend调用；保留auth/login、users/me、user-model、health、annotated-pdf等既有单数/动作型契约，不为规范重命名 |
| B03 响应 | 成功直接返回DTO/分页对象；失败只用下方error包络，调用方复用api.ts；不增加第二套`code:0,data`成功包络 | 正常、422、401、404、409各抽一个；204无正文，PDF/图片二进制及流式响应不套JSON；检查Content-Type、X-Request-ID |
| B04 错误码 | 使用有语义的UPPER_SNAKE_CASE字符串，按下表分类；新码必须在本页登记HTTP/触发/恢复行为，并同步领域API文档/测试 | 从reject/fail/ModelFailure路径找实际返回，与登记比对；不能用中文message判断业务分支，不能将500通用兜底当正常失败覆盖 |
| B05 参数校验位置 | 结构/类型/长度/枚举在Pydantic/Query/multipart边界；业务再核验owner、版本、真实页数、状态。InputModel默认拒绝额外字段；新增query显式拒绝未知/重复参数 | 传缺字段、未知字段、错误类型及越界值应按契约400/422；检查schemas.py与领域InputModel，不能只靠TS/按钮禁用 |
| B06 数据访问/事务 | SQLAlchemy参数绑定；一次业务变更与版本/收据同事务。唯一约束兜底去重；失败rollback并保留原件。迁移只通过Alembic，编号串行，禁止API中create_all | 注入commit失败检查记录、版本、文件补偿；核对models/迁移及test_documents/test_annotations。新库upgrade head及重复head；MySQL另证 |
| B07 事务内禁止项 | 新业务不在持锁事务中等待模型HTTP、上传、渲染等长操作；外部副作用明确超时、取消和补偿。需要可靠异步投递时先设计Outbox/事件表，不把BackgroundTask当持久队列 | 审查begin/with_for_update/commit之间的HTTP/IO；失败注入验证副作用。现有PDF原子发布、导出快照/短锁内复制是兼容例外，不能称已有通用Outbox |
| B08 幂等/并发 | 每个新写接口在change/API说明重复、超时未知结果、冲突行为；存储约束+CAS保证，不能仅先查再写。409不自动用新版本覆盖 | 同请求重复/同ID不同内容/两并发写三种检查；既有机制见下表；没有全局Idempotency-Key中间件 |
| B09 分页/排序/筛选 | 沿用page/pageSize，文献默认20上限100、笔记上限50；非法超限现有422，不照搬样例静默截断。字段/方向走白名单 | 核对documents/library/notes的Query与DTO；传超上限、非法sort/order应拒绝，不返回扩大的集合 |
| B10 唯一兜底排序 | 非唯一业务排序键后追加主键，空值排序语义明确；不得只按标题/时间分页 | 同名、同时间记录跨两页检查无重复/遗漏；现有library.py排序末尾Document.id，notes也使用id兜底 |
| B11 非法筛选失败 | 未知字段、重复键、非法年份/标签/文件夹/类型必须明确拒绝，不能忽略后返回全量；新增列表继承此策略 | 对比合法与非法查询，不得数据范围扩大；现有文献allowed集合检查，其他历史端点未全部集中校验，修改时补证 |
| B12 配置外置 | 配置经config.Settings/ModelSettings读取部署变量/后端私有.env；机密无有效默认值。非秘密安全默认值可保留；可选模块缺配置明确禁用/503，核心必需缺失启动失败 | 删除DATABASE_URL/SESSION_SECRET验证Settings失败；production须HTTPS+Secure；模型缺配置不伪造成功。见test_auth及config.py |

## v1响应与错误登记

```json
{"error":{"code":"VALIDATION_ERROR","message":"请检查输入内容","details":{"fields":[]}},"requestId":"随机请求标识"}
```

`details`按需存在；`X-Request-ID`用于关联，API设置no-store。成功DTO不强加requestId正文；以HTTP状态、错误code及数据副作用联合判定，不能照搬“所有接口HTTP200”的测评假设。

以下是跨模块核心码登记；完整的既有领域码及参数恢复细则仍以 [API契约](../design/api-contracts.md)、Litera-test的`docs/delivery/team-integration.md`（随模块交付，原Litera尚无此文件）和对应生产者为准，未在本表逐项列出的历史领域码不是本次新增。新码不得仅加入代码而遗漏登记。

| 分类 | HTTP / 已有码 | 触发与恢复 |
| --- | --- | --- |
| 参数 | 422 VALIDATION_ERROR、INVALID_QUERY | 结构/查询非法；修正字段，保留合法输入 |
| 认证 | 401 UNAUTHENTICATED、INVALID_CREDENTIALS | 缺失/过期会话或登录失败；登录失败文案不区分邮箱是否存在 |
| 请求来源 | 403 INVALID_ORIGIN、INVALID_CSRF_TOKEN | Origin/CSRF失败；从配置对应入口刷新后重试 |
| 私有资源 | 404 DOCUMENT_NOT_FOUND、NOTE_NOT_FOUND、PDF_NOT_FOUND | 普通资源不存在/他人/已删按对应资源相同语义处理；不回显存储路径 |
| 业务冲突 | 409 EMAIL_EXISTS、DUPLICATE_DOCUMENT、VERSION_CONFLICT、ANNOTATION_REVISION_CONFLICT、NOTE_VERSION_CONFLICT | 重复/陈旧版本；核对已有记录或服务器版本，不自动覆盖 |
| 账号安全 | 400 INVALID_CURRENT_PASSWORD、PASSWORD_UNCHANGED | 当前口令错误/新旧相同；保留会话并修正，不当成全局401 |
| 文件 | 413 UPLOAD_TOO_LARGE；415 INVALID_PDF、ENCRYPTED_PDF；416 INVALID_RANGE | 大小/格式/加密/范围非法；明确上限或修复/解密文件后重试 |
| 模型/能力 | 503 MODEL_NOT_CONFIGURED、TRANSLATION_NOT_CONFIGURED、MODEL_VAULT_UNAVAILABLE、NOTES_NOT_READY；422 MODEL_URL_UNSAFE | 未配置/未部署/不安全地址；按环境配置修复，不回退Mock或其他人的Key |
| 容量/超时 | 429 AUTH_RATE_LIMITED、EXPORT_BUSY；504 MODEL_TIMEOUT、EXPORT_TIMEOUT | 等待后重试或取消；未知提交结果先核对幂等收据，不盲目新建 |
| 内部故障 | 500 INTERNAL_ERROR | 最后兜底；对外不含堆栈，保留requestId调查；不得据此宣称负向用例已完整处理 |

## 既有写入机制与生命周期

| 能力 | 重复/并发约定与实现依据 |
| --- | --- |
| PDF上传 | 同owner+SHA256唯一；重复409而非生成第二篇。原子临时文件发布/数据库失败补偿；`save_upload`和test_documents |
| 题录/进度 | 显式version CAS；并发一胜一冲突；GET详情不冒充一次阅读写入 |
| 批注 | commandId+baseRevision+对象version；收据重放相同请求，变体冲突；24小时收据期限，见annotations.py |
| 笔记/摘录 | 笔记UUID重放、version CAS；摘录operationId去重。关联M:N，解除关联保留独立笔记，删除与软删/永久清理不混同 |
| 个人模型 | expectedRevision/配置revision防旧写覆盖；改地址/模型/Key撤销验证，测试完成再复核revision；删除不删既有译文笔记 |
| 导出 | 指定expectedAnnotationRevision取已保存快照；受保护同步二进制，不承诺通用异步作业/百分比进度 |

## 迁移及现有例外

- 迁移链当前0001–0008；0007/0008已占用，不复用编号、不修改已交付迁移历史来迁就新模块。
- “迁移可重跑”指Alembic版本跟踪下重复upgrade head不变，不要求把脚本改写成MySQL不支持的通用IF NOT EXISTS语法。
- 课堂要求回滚验证，Litera已有保护性例外：0007拒绝删除笔记表，0008存在配置时拒绝drop。新迁移必须声明可逆性；不可逆时先在独立副本验证备份恢复/兼容退应用，不强行downgrade业务库。
- 接口层与业务层尚未完全分开、成功响应未套统一包络、公共动作端点单数是明确兼容例外。下一次需要不兼容调整时单独设计版本和消费者迁移；不是本次重构任务。

违反时记录Bxx、路由/函数、实际与预期、影响消费者及检查结果；新接口不得靠“历史也这样”逃避增量约束。规范只能静态发现分层/命名问题，事务与并发需行为测试，不把文档审查当运行证据。
