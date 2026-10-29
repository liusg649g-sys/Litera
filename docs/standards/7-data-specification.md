# 7-Litera 数据规范

> 跨仓适用说明：规范约束两仓后续开发，本文实现快照来自Litera-test。原Litera目前仅01/02、迁移至0006；03/04/07及0007/0008尚未合并，相关“现有”描述只属于Litera-test，在原项目按待接入要求理解。文件同步不等于代码、脚本或部署已合并，先查本仓实际文件；总表见[规范索引](README.md)。

适用：关系库、私有PDF/图片、笔记来源及其副本。依据第7课[数据规范](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/std-data.html)和[完整样例](https://devops.hello1023.com/课件/第7课-课件-小组项目启动/pages/case-data.html)。2026-10-28按当前Litera-test审订；“现有”不等于本轮实测，“增量要求/待落实”不假报已实现。

## 1. 总则与技术基线

| 维度 | 当前事实 |
| --- | --- |
| 数据库/ORM | Compose使用MySQL **8.4**、utf8mb4，SQLAlchemy 2.x；隔离测试可用SQLite，不证明MySQL锁/精度通过 |
| 迁移 | Alembic，backend/migrations/versions，当前链0001–0008；不执行业务库迁移来检查文档 |
| 标识/时间 | 多数实体String(36) UUID；有复合键、document_id/owner_id主键。UTC naive datetime存库，API转带Z的ISO8601；只有部分字段使用DATETIME(6)，不是全库微秒精度 |
| 文件/类型 | PDF_STORAGE_ROOT控制根路径，宿主默认storage/pdfs，Compose默认/data/pdfs。JSON还用于收据result等；摘要当前Text，笔记/批注长正文有MEDIUMTEXT变体，不强改类型 |

查询/事务/CAS见[后端规范](2-backend.md)，机密与日志见[安全规范](3-security.md)。备份恢复执行归运维，本页声明生命周期和副本。

## 2. 九项规范条目

### 2.1 命名与类型（D01）

- **现有**：表/列snake_case，API camelCase；reading_progress/document_reader_state等为既有单复数例外。索引/约束用ix_/uq_，字段长度/空值/默认值显式。
- **增量要求**：新状态列说明枚举与允许转换；JSON或独立列按查询需求选择。已有authors/keywords/sources参与搜索，不规定“可查询字段禁止JSON”。
- **检查**：比对models.py的mapped_column、迁移与§4；不使用本项目不存在的db.Column检查口径。新短String无长度、同义混名需整改。

### 2.2 主键、外键与归属（D02）

- **现有**：主键/owner例外见§4；sessions用user_id，个人模型owner_id即主键。不能强制所有表新增id/owner_id。
- **增量要求**：资源可可靠取得所属用户，跨资源核验双方及关联。外键删除行为按生命周期选择；document_files.document_id当前无ondelete，由清理服务显式删除，不能宣称全CASCADE。
- **检查**：核对ForeignKey/ondelete和实际删除逻辑；A/B账号互换ID，普通私有资源与不存在维持相同404业务语义（排除requestId）；不能把前端或外键当授权。

### 2.3 审计字段（D03）

- **现有**：documents/notes等有created_at/updated_at/version；sessions有created_at/expires_at/revoked_at；文件/关联/状态/收据并非全有审计三件套。version起值按契约，个人模型用UUID revision。
- **增量要求**：新可编辑实体明确创建者/owner、时间及并发策略；只读附件/关联可说明最小字段例外，不为统一形式修改历史表。
- **检查**：按实体职责查写路径；改密同事务更新password_hash/updated_at并撤销本人会话。审计追加保留不等于禁止业务字段正常更新。

### 2.4 迁移纪律（D04）

- 已交付迁移只增不改，新revision接当前head；0007/0008已占用，跨分支先协调编号。
- 可重跑指版本跟踪下重复`alembic upgrade head`不改变数据，不是直接重执行upgrade函数；op.alter_column的existing_type不能保证幂等。
- 0005/0006/0007主动拒绝downgrade，0008有配置时拒绝drop，属于数据保护，不要求无条件降级成功。新迁移声明可逆性/兼容退应用/恢复方案。
- **检查**：只在临时库验证旧数据升级、重复head；可逆迁移在副本降升，保护迁移验证拒绝且数据不变。真实MySQL在隔离实例/专用litera_test另验，禁止对业务库执行降级演练。

### 2.5 数据字典（D05）

- §4提供当前表级/关键字段索引；语义参考[数据模型](../design/data-model.md)、models/迁移及Litera-test的`docs/delivery/team-integration.md`（随模块交付，原Litera尚无此文件）。数据模型中历史head0006/03未实现不覆盖当前0008事实。
- 新字段的业务语义在数据模型维护一处，API定义暴露DTO并引用；同步本页索引/对应change，不要求四份文档复制相同定义。specs可列验收所需枚举。
- **检查**：新表/字段可定位含义、类型、约束、归属、消费者；不引用不存在的“第4节完整字典”或docs/design/data-specification.md。

### 2.6 敏感分级与脱敏（D06）

| 级别 | 数据 | 允许行为 |
| --- | --- | --- |
| 公开 | 品牌、帮助、公开规范、安全错误说明 | 可公开，不包括用户记录 |
| 内部/私有 | 文献题名/作者/期刊、笔记标题、分类、资源ID | 仅授权本人接口返回；元数据不是公开数据 |
| 敏感内容 | PDF/选区/笔记正文、译文、回答、来源块 | 仅授权业务接口返回；不记录正文片段到日志，不能“先截500字” |
| 凭证/机密 | 密码/哈希、会话token/hash、API Key/密文、主密钥 | 不进业务响应/URL/日志；口令哈希、Key认证加密，状态仅hasApiKey等 |
| 个人信息 | email、display_name、会话关联 | 本人认证/资料接口按契约返回；测试导出脱敏；当前无自动账号注销/法规删除工作流 |

- 引用[安全S07/S12](3-security.md)，不另立脱敏实现；token_hash是会话索引，不是通用日志脱敏器，当前不存在扫描全部请求体的集中脱敏中间件。
- **检查**：以合成占位凭证触发错误，核对响应/日志无原值、hash、密文与全文；422只回字段/类型。全日志审计待落实。

### 2.7 留存与删除（D07）

| 数据/副本 | 当前机制与期限 | 边界 |
| --- | --- | --- |
| 文献/PDF/笔记 | 无自动年龄到期；本人显式删除。软删保留、可恢复；永久清理保留独立笔记正文/sources | 原件不能被导出覆盖；解除关联不删笔记 |
| sessions | 默认有效期86400秒，可配置；退出/改密撤销；无统一过期行物理清理任务 | 撤销不等于立即删除审计行 |
| 批注墓碑 | 支持undo/redo，随文献永久清理；无通用新写自动删墓碑机制 | 与命令收据清理不同 |
| 命令收据 | 有效期24小时，GET过期拒绝；同文献写入清理过期收据 | 非全库准点清理承诺 |
| 图片资产 | 未引用上传1小时；末次活动引用删除/替换后24小时；活动引用expires_at=null；启动/周期扫描 | 删文件后标deleted保留台账；文献永久清理再删行 |
| cleanup_jobs | 保留状态/attempts/error审计；完成storage_key=null | 无统一审计到期清理策略 |
| 模型配置 | 本人删除行及密文，已有笔记/译文保留 | 备份可能仍有密文，不能说“无额外副本” |
| sessionStorage草稿 | 当前账号浏览器会话范围，服务端不能远程保证擦除 | 退出/共享电脑另查残留，不把草稿当已保存 |
| 日志、数据库/PDF备份、卷副本 | 尚未统一留存期限/到期任务；删除请求须登记原因、到期日期、执行人 | 待运维落实；不擅自删备份，恢复前复核已删数据不会重新提供 |
| 未来向量/分块/缓存 | 05/06未接入 | 接入前列期限、删除/重试和所有副本 |

**检查**：在隔离样本执行创建→软删→恢复→永久清理，按表核对行/文件/关联、独立笔记、浏览器/日志/备份。未配置期限不得声称自动删除；故障注入只在临时副本，不kill在线容器或改用户PDF权限。

### 2.8 跨存储一致性（D08）

**PDF上传实际顺序**（documents.save_upload）：流式写临时文件/算SHA256→fsync/结构校验→查重复→添加/flush文献和附件、唯一约束兜底→os.replace发布文件→DB commit→refresh返回。不是“DB提交后再写PDF”。失败rollback/回收临时文件；commit回执丢失先核对已提交行，不能误删PDF。硬退出孤儿文件全量对账仍待落实。

**永久清理实际顺序**（library.run_cleanup）：提交清理意图/purge标记→CAS领取running并持久化租约→持锁删资产/PDF（missing_ok）→显式删资产/收据/批注/状态/关联/文献行→标completed、storage_key=null并commit。DB失败回滚后标failed；文件已不存在仍可重试收敛，不是一律人工重建文件。

状态只有pending/running/completed/failed；running租约过期是重新领取条件，不是lease_expired状态。failed重试/过期重领回running；202尚未完成，204已完成。

**图片资产**：先提交uploading台账→重新核验文献锁/状态→写图片→ready。清理先提交cleaning，再删文件/标deleted，失败可重试；不是先删DB行。

**检查**：复用test_documents磁盘/提交故障与回执丢失、test_library清理重试、test_reader_assets台账竞态；断言原件保留或最终清理及状态，不只看HTTP。

### 2.9 测试数据隔离（D09）

- conftest默认临时SQLite文件/PDF目录；显式TEST_DATABASE_URL仅接受litera_test库名，fixtures会清表，仍须核对主机/实例隔离。
- 不要求测试后DROP DATABASE，不清业务卷。只用合成/脱敏样本，用户为阅读导入的论文不是自动测试fixture。
- APP_ENV=test不令所有Settings忽略.env；隔离脚本显式覆盖业务变量，ModelSettings测试时不读开发者私有.env。
- **检查**：核对URL、临时路径、清理范围；fixture占位Key仅用于受控替身。结果注明SQLite/MySQL、Mock和跳过原因。

## 3. 项目特有并发与机密约定

- CAS为Compare-and-Swap；各实体version、集合annotation_revision、模型revision互不替代。更新条件带owner/资源/原版本；冲突使用既有码409（如VERSION_CONFLICT/NOTE_VERSION_CONFLICT），不使用漏owner的示例。
- 相同commandId/指纹重放收据，变体/旧版本冲突；摘录operationId另有去重。文件hash不能代替用户归属。
- Key在Windows可用DPAPI，文件Vault用AES-GCM，依OS/配置选择；不可用/方案不匹配拒绝，不回退明文。跨机/主密钥轮换无通用自动工具。

## 4. 当前数据字典索引

具体类型/约束证据：[models.py](../../backend/app/models.py)、[迁移](../../backend/migrations/versions)。本表为索引，不复制DDL，新增字段语义按D05维护。

| 表 | 主键 / 归属 | 用途与关键约束 |
| --- | --- | --- |
| users | id / 本人id | email唯一、password_hash/display_name、创建/更新时间 |
| sessions | id / user_id | token_hash唯一、expires_at/revoked_at |
| documents | id / owner_id | 题录、version/parse_status、deleted_at/folder_id/purge_job_id |
| document_files | id / owner_id+document_id | 原名、私有storage_key/hash/大小；owner+sha256唯一；显式清理 |
| folders、tags | id / owner_id | name/normalized_name，owner内唯一；标签颜色 |
| document_tags | document_id+tag_id / owner_id | 两端FK CASCADE；无统一id/审计全套 |
| reading_progress | document_id / owner_id | 页码/缩放/视图/last_read_at/version |
| cleanup_jobs | id / owner_id | document_id无文献FK；状态/attempts/租约/error审计 |
| annotations | id / owner_id+document_id | type/geometry/style/position/正文/asset_id/version/墓碑；资产由应用核验 |
| document_reader_state | document_id / owner_id | annotation_revision集合版本 |
| annotation_command_receipts | document_id+command_id / owner_id | fingerprint/result JSON/expires_at |
| reader_assets | id / owner_id+document_id | 文件键/hash/尺寸/状态/attempts/expires_at |
| notes | id / owner_id | 独立身份、纯文本正文、version、source_schema_version/sources |
| note_documents | note_id+document_id / owner_id | M:N、created_at；两端FK CASCADE |
| user_model_profiles | owner_id / 同主键 | revision/provider/base_url/model、encrypted_key/scheme/tested_revision/updated_at |
| alembic_version | version_num / 非业务资源 | Alembic维护，不添加虚假owner/审计字段 |

## 5. 合规检查清单

- [ ] D01–D03：类型、键、owner/审计策略与实际模型一致，既有例外明确。
- [ ] D04–D05：迁移不改历史、隔离验证重复head/保留数据，保护性回退不破坏；字典与DTO语义一致。
- [ ] D06：私有元数据不公开，凭证/正文不进日志，引用安全规则。
- [ ] D07–D08：列全副本、期限与待落实项；失败可重试，不误报完成。
- [ ] D09：测试库/文件/凭证隔离，SQLite与MySQL证据分开。

违反时记录Dxx、位置/流程、实际与期望、验证结果；修正文档不等于改库。本次未执行迁移、删除演练或更改业务数据。
