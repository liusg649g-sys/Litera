# P1 登录注册 UI 优化验收

日期：2026-10-14。范围：现有登录注册页面、共享主题及01认证规约；不改后端认证，不增加其他模块。

## 修改

- AuthPage使用Element Plus原生validateField/提交验证，关闭规则变化及输入组件自动校验事件。首次、聚焦和未提交空值失焦不报错；非空内容失焦校验；输入修改清除对应旧错误；切换模式在nextTick后清空校验及密码。
- theme.css集中Primary #9B0000、Hover #B82A2A、Active #750000、浅红#FFF4F4、页面#F7F8FA及卡片#FFFFFF，映射Element Plus品牌色，状态色独立。
- Brand内联SVG继承主题；favicon有与Primary一致的静态回退，浏览器theme-color从CSS Token读取。
- 保留左右分栏，减少页头/卡片/表单间距，注册保留min-height，登录按内容撑高，字段底部留提示空间；窄屏保留自然滚动。
- 更新UI规范、user-auth需求场景、01设计/提案和UI任务；不重新生成六个change。
- 原认证Cookie、CSRF、Origin、密码哈希及API格式保持不变。

## 验证

| 检查 | 结果 |
| --- | --- |
| vue-tsc与Vite生产构建 | 通过 |
| Vitest基础回归 | 7通过 |
| 新UI浏览器测试 | 10通过 |
| 既有真实认证回归 | 2通过 |
| OpenSpec strict | 六个change通过，无问题 |
| 旧品牌色及相关硬编码 | 源码与规约搜索无残留 |

UI测试在本地Vite的5174端口检查最新源码；仅隔离匿名会话探测和指定错误响应，用于UI状态及请求契约验证。真实认证回归针对用户已运行的8080 Nginx/FastAPI/MySQL服务，二者分开报告，不把替身当作业务实现。

覆盖首次无红框、空值聚焦失焦、输入期间安静、非法值失焦、提交拦截、修改清除、确认密码、模式切换、合法注册DTO、服务端错误保留输入、Logo/按钮/标签/链接/聚焦Token、按钮hover/active及独立状态色。

布局检查1280×720、1366×768、1920×1080完整注册首屏、登录内容间距与切回注册布局恢复；390×844和360×560无横向溢出、完整字段/按钮可滚动访问。已视觉检查桌面与窄屏截图；截图仅作本地测试产物，不提交。

最近验证：前端构建、Vitest 7项、auth-ui 10项及六个OpenSpec严格校验均通过。五种尺寸注册截图前后完全一致；真实认证2项为此前验收结果，最近布局验证未重新执行该套测试。

## 用户验收

本轮未执行Docker构建或启动、未修改Docker全局配置、未commit/push。现有Docker镜像不会自动包含最新UI，请在项目根目录用CMD手动执行：

    docker compose up -d --build --wait

刷新 http://localhost:8080/login 和 /register 体验。仅跑本地UI测试可在frontend目录执行：

    npm run test:e2e -- --project=auth-ui

用户已认可注册页、文献库占位页和个人资料页；当前登录布局已完成修复。下一轮任务为文献库主界面开发，本次未开始。
