# 翻译与笔记交付：部署与迁移

本文为组员获得批准、拉取交付分支后的操作说明；本轮未执行Docker命令或迁移业务库。当前5183保持已验收运行版本，兼容补丁只在隔离测试加载。

## 环境与默认模式

- Python3.12、Node24；复用backend/requirements.txt与frontend/package-lock.json，不手动升级依赖。新增AES使用已有cryptography50.0.2，不新增依赖。requirements.in补回已存在的pypdf/Pillow/reportlab/multipart/psutil直接依赖，避免未来重生成锁文件遗漏。
- Windows `USER_MODEL_SECRET_BACKEND=auto`继续当前账号DPAPI，不读取主密钥文件、不转换已有密文。
- Linux auto无文件时禁用个人模型；显式`aesgcm_file`加独立`USER_MODEL_MASTER_KEY_FILE`启用文件Vault。密钥缺失/长度错误/POSIX宽权限/坏密文安全拒绝，不能改成明文。
- 普通团队部署默认不开启Mock或模拟问答。显式的隔离验收脚本才开放固定Mock；正式QA仍503未接。个人模型失败不回退开发者；开发者模型只在管理员自行明确配置和授权后使用。
- `LITERA_DISABLE_DEVELOPER_MODEL=1`阻止读取backend/.env并隐藏默认模型选项；它不是密钥清除器，环境变量显式AI_*仍是服务端配置。统一5183另有UNIFIED_ACCEPTANCE阻止developer调用。团队不要将开发者Key填作所有用户共享配置。

## Linux新实例（管理员手动；不要复用现有业务项目名/卷）

以下生成配置/编辑步骤只在**全新克隆且没有既有.env或业务数据**的目录操作。若当前目录已有.env，不按下文编辑它：另建独立的私有配置文件，并在所有Compose命令明确增加`--env-file /absolute/private/litera-integration.env`；保留原配置与部署，涉及既有目标按后文升级审批。

1. 先确认目标端口、项目名、数据卷隔离。建议全新`litera-integration`，端口8084；Compose无固定container_name，`-p`覆盖文件中的name:litera。不能去掉-p而误启动旧项目。
2. 在仓库外准备私有目录和随机主密钥。以下仅示例，必须选择管理员拥有的私有位置：

```sh
mkdir -p "$HOME/.config/litera-secrets"
chmod 700 "$HOME/.config/litera-secrets"
python scripts/init_model_key.py --output "$HOME/.config/litera-secrets/user-model-master.key"
```

生成器拒绝仓库/构建上下文内路径、拒绝覆盖已有文件，内容不打印。文件为随机32字节的base64；POSIX创建0600。主密钥和数据库分别备份，备份也不能提交Git。主密钥丢失无法解密，禁止直接替换后声称旧密钥已迁移。

3. `python scripts/init_env.py`只在不存在.env时生成数据库/会话秘密；已有.env保持。只在本地编辑需要的条目，不覆盖整个文件：

```dotenv
APP_PORT=8084
PUBLIC_ORIGIN=http://localhost:8084
USER_MODELS_ENABLED=true
USER_MODEL_SECRET_BACKEND=aesgcm_file
USER_MODEL_MASTER_KEY_SOURCE=/absolute/private/path/user-model-master.key
```

真实主密钥和用户API Key均不填到示例。外部主密钥源由可选override挂载为`/run/secrets/user_model_master_key`，后台文件路径由override设置；只对api开放，db/nginx不获取主密钥。主机源文件需600/400；不要只依赖Compose的mode声明，应核对容器内权限。对文件来源的Compose secret，uid/gid/mode可能受底层bind mount限制，见[Docker服务secrets说明](https://docs.docker.com/reference/compose-file/services/#secrets)。本轮没有运行Docker验证具体平台权限。

4. **只有管理员确认是全新独立卷后**，才执行未来部署命令：

```sh
docker compose -p litera-integration -f compose.yaml -f compose.user-models.yaml up -d --build --wait
```

API Dockerfile在启动时执行`alembic upgrade head`，这是实际迁移行为；不是只读启动。随后仅通过PUBLIC_ORIGIN对应的`http://localhost:8084`操作，别切换127.0.0.1而触发Origin/CSRF校验。

5. 检查新实例健康和最小原生依赖：

```sh
docker compose -p litera-integration -f compose.yaml -f compose.user-models.yaml ps
docker compose -p litera-integration -f compose.yaml -f compose.user-models.yaml exec -T api python -c "import cryptography, pypdfium2; print('runtime imports ok')"
docker compose -p litera-integration -f compose.yaml -f compose.user-models.yaml exec -T api python -c "from app.model_secrets import get_secret_vault; print('vault available:', get_secret_vault().available)"
```

这些检查不打印Key。若Vault不可用，先修正受限文件挂载/权限，不放宽密钥检查。Nginx需要实际构建；lock已有Linux x64/arm64 musl和GNU Rolldown可选绑定，Windows构建通过仍不等于Alpine已构建。

6. 注册独立账号→个人资料→AI模型设置→填写自己的地址/模型/Key→保存→主动测试→PDF选区翻译选择“我的模型”。真实请求由使用者主动发起；保存、查询、页面加载不发模型请求。错误Key/模型404/超时/429应给出脱敏错误，不回退共享Key。

## 已有数据升级：必须另行确认

顺序是0001→…→0006_reader_assets→0007_literature_notes→0008_user_model_profiles；本轮无0009。0007新建notes/note_documents，0008新建用户配置，不改旧文献/用户/批注列。后续组员不得重复使用0007/0008编号。

升级既有部署前：正常停写→数据库与PDF/图片联合备份→清单/大小/SHA256→在独立副本恢复并检查完整性/外键/原记录数量→单独验证迁移→管理员确认后升级目标。旧库/MySQL锁与精度行为本轮未实测，不能把离线DDL当MySQL通过。

回退原则：保留新增表、先退应用或停止新功能；0007明确拒绝破坏性downgrade，0008有配置时也拒绝drop。禁止down -v、prune、覆盖恢复或自动转换真实Key。失败保留现场与备份，先查日志，不连续重建。

DPAPI密文不可直接跨Windows账号/主机或搬到Linux解密。当前协议不匹配会拒绝调用，用户可在新部署明确重新输入自己的Key；这不是自动迁移。真实密钥迁移、主密钥轮换、KMS接入和旧Key重新加密均须单独批准，并先做私有副本验证。

## 可复现的隔离检查（不使用现有业务数据）

先安装锁定依赖，Windows用backend/.venv/Scripts/python.exe，Linux用backend/.venv/bin/python，下列python均指该venv解释器。Node依赖用frontend内npm ci，浏览器依赖按Playwright安装。检查入口：

```sh
python scripts/verify_delivery.py backend
python scripts/verify_delivery.py frontend
python scripts/verify_delivery.py build
python scripts/verify_delivery.py browser
```

脚本强制独立临时SQLite/PDF/TMP，后端阻断外网，清除模型/主密钥继承配置，使用固定受控HTTP/Mock。构建到`.cache/github-delivery/frontend-dist`，不会覆盖在线frontend/dist；浏览器采用临时AES文件，不读取真实主密钥或backend/.env。五组浏览器单worker，1GB Node堆、原10GB磁盘门槛。实际测试结果见交付总报告。

Windows已有scripts/litera.ps1是本机旧5180数据副本导入专用；新克隆没有那份数据时应使用本节测试或新实例部署，不能从他人电脑复制数据库/密钥备份来凑启动条件。

## 尚未验证

本轮仅Windows环境实际运行AES/DPAPI/临时SQLite/Chromium；POSIX权限专项在Windows跳过，Linux镜像构建、Linux运行、真实MySQL、服务商质量/费用及真实QA联调均未执行。密钥算法使用[cryptography AESGCM](https://cryptography.io/en/latest/hazmat/primitives/aead/#cryptography.hazmat.primitives.ciphers.aead.AESGCM)，按文档使用随机96bit nonce及关联数据，不重复nonce或截断tag。
