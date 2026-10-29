---
name: litera-standards-review
description: Review Litera artifacts against its eight engineering standards, including lesson-7 coverage and repository-specific implementation evidence. Use for a requested standards review or acceptance check; does not replace OpenSpec planning, implementation, or deployment.
---

# Litera 工程规范审查

输入：待审查的diff、change名或具体文件范围；可选的运行环境与允许执行的检查。范围不明时先审查当前diff，不自行扩大到重构或部署。

1. 读取项目根目录AGENTS.md和docs/standards/README.md，再按范围选择1–8规范。路径均相对项目根目录；条目ID/章节和例外以这些文件为唯一来源，不默认全部加载。
2. 记录已有Git改动。先区分当前是Litera还是Litera-test：03/04/07及对应迁移/脚本尚未合入前者。核对本仓实际源码、迁移和OpenSpec场景；区分实现、开关、Mock和未合并模块，不能用另一仓的测试结果冒充当前验证。现有openspec-*技能继续负责规划/实现/归档，不复制其步骤。
3. 将每项改动映射到规范条目ID或章节，检查适用约束、现有例外和消费者。新增API查授权/错误/重试与冲突，页面查场景/四态/组件，测试查隔离/有效断言，运维查实际启动副作用/恢复，AI查来源/参数/质量证据，数据及评审查兼容与完成判定。
4. 选择能证伪结论的最小检查：如A/B账号换ID、同命令重放、并发旧version、空/错/正常视图。先检查测试隔离，禁止让fixtures清理业务库；不替用户调用真实模型、轮换Key或迁移现有库。检查入口见docs/standards/8-review-specification.md第3节，历史验证结果见HANDOFF.md。
5. 需要验证规则能发现违规时，只向临时/内存样本注入一个反向依赖、缺owner校验或自造视觉样式，指出对应ID和证据。不得修改工作树业务代码来制造故障。样本审查不等同真实变更回归，也不等同独立新会话验证。
6. 输出：条目ID、文件/位置、期望与实际、证据、通过/不通过/不适用/待验证、建议处置。运行检查附命令、环境、退出码；未运行和未授权的动作明确保留，不假报通过。最后核对diff未越过授权范围。

发现问题不自动修复；用户已授权修复时可继续对应开发工作流。审查授权本身不授予提交、推送、发布或改动业务数据的权限。
