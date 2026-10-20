# 个人资料：修改密码

2026-10-20，用户明确授权的账号安全小增量；独立于P3-C2实际功能/UI验收，不改变Change 02的35/36状态。

## 行为

- 入口：文献库右上「个人资料」→「账号安全」→「修改密码」。页面内展开，无中央弹窗。
- 当前密码、新密码、确认新密码均必填；沿用默认8–128字符，不裁切空格，支持Unicode。
- 初次展开/空值失焦不报错，提交统一校验；修改错误字段清除旧提示，当前密码错误留在原页。
- 取消清空密码并收起，输入只存在组件内存，不放入URL或本地存储；未确认输入阻止静默路由离开。
- 保存时防止重复提交并禁用关联表单；失败可修改重试，网络未知结果不宣称成功。
- 成功更新密码哈希并撤销本人全部会话，清Cookie与前端认证状态，回登录页提示「密码已修改，请重新登录」。
- 其他账号及已有文献、批注、资产不变；不做忘记密码/邮件找回，不新增数据库迁移。

## 接口与一致性

`POST /api/v1/auth/password`接受currentPassword/newPassword，复用Cookie/Origin/CSRF和认证IP限流。
错误密码400 INVALID_CURRENT_PASSWORD，新旧相同400 PASSWORD_UNCHANGED，非法422，无会话401、来源/CSRF403、限流429。
更新users.password_hash/updated_at及撤销sessions在同一事务；提交失败一并回滚。
登录与修改密码统一先锁本人User；修改时对当前Session再作当前读，避免旧密码登录/旧会话在等待后绕过撤销。
MySQL实际锁并发集成未执行，不能把SQLite功能测试称为MySQL并发通过。
详细契约见[API](../design/api-contracts.md)。

## 实际验证

| 验证 | 结果 |
| --- | --- |
| 后端认证专项 | 31/31，`.cache/password-api.log`；含多设备撤销、其他用户保留、Unicode/空格、旧密码拒绝/新密码登录、非法/CSRF/Origin/限流及提交失败回滚 |
| 后端全量 | 191/191，临时SQLite/真实迁移，87.52秒，`.cache/password-backend-full.log`；不连接开发数据库 |
| 前端类型与生产构建 | 通过，`.cache/password-build-final.log`；既有ReaderPage >500kB提示保留 |
| 既有前端单测 | 65/65，`.cache/password-unit.log` |
| 生产真实认证浏览器 | 3/3，`.cache/password-browser-final.log`；注册/登录/资料/退出守卫回归，以及密码校验/取消清空/离开保护/错误密码/网络失败恢复/390px/多设备失效/新密码重新登录 |
| MySQL | 未执行，未操作业务MySQL或数据卷 |
| 用户部署后的实际体验 | 待用户验收，不用自动化替代 |

OpenSpec严格校验6/6、git diff --check通过；主规格未同步，未归档。

浏览器首轮有一次测试定位过宽，getByRole(alert)同时命中字段错误与服务端提示；已限定账号安全错误栏后复测。
截图检查使用字段校验完成后的状态，桌面与390px无中央遮罩及横向溢出。截图在忽略目录frontend/test-results/reader下。
保留既有Starlette/httpx弃用、Node颜色变量及构建体积提示。

## Windows CMD 手动部署

在项目根目录由用户执行（本轮未运行Docker）：

```cmd
docker compose up -d --build --no-deps --wait api nginx
```

Ctrl+F5后从个人资料进入；用当前密码与不同的新密码保存，确认回登录页，新密码能登录、旧密码失败，其他设备旧会话失效。
不重新生成.env、不重建数据库、不删除数据卷。无commit/push/OpenSpec sync/archive。

本地复验（已安装依赖；临时SQLite）：backend目录运行`.venv\Scripts\python -m pytest -q`。
frontend目录运行`npm run build`、`npm test`，再设置`LITERA_READER_PRODUCTION=1`及`LITERA_READER_AUTH=1`后运行`npm run test:reader`。
