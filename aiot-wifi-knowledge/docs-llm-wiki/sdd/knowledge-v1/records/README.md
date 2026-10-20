# 实际开发与验收记录

当前部署先读[布局与部署记录](workspace-layout-20261020.md)及 `traceability.json.current_deployment`：程序、工具和依赖已移至仓外，仓内保留架构骨架。下列记录按原实现和原发布身份保留，历史 230 项合成测试与 verified 状态不代表当前 checkout 可运行。

- [T01 开发记录](T01-development.md)：公开 CLI、四类契约与声明范围，含实际 red 与环境问题区分。
- [T02 开发记录](T02-development.md)：真实路径、Git 身份、工具实际读取、中文 CLI 与竞态分支。
- [审查记录](review.md)：Standards 与 Spec 两轴，固定候选、发现、修复及复验。
- [首批验证结果](first-batch-verification.json)：实际环境、命令、测试结果、边界及后续任务。
- [T03 raw 捕获验收](T03-verification.md)：单仓集成、原字节与持久证据恢复、支持格式和独立审查。
- [T05 候选与最终视图验收](T05-verification.md)：七类显式卡、计划与物化、来源绑定及独立审查。
- [T06 人工确认验收](T06-verification.md)：交互终端挑战、确切视图绑定、部分接受新视图和限制。

[T07 事务与当批最终验收](T07-verification.md)保存当时干净回归、两轴审查与实现边界；[手工操作链](../document-chain-usage.md)仅说明历史公开接口。逐模块历史发布身份见[发布回执](publication.json)，不从目录或测试数量推断真实业务已接入。

首批原始功能 red 保存为 T01-red.txt，首批 JUnit 为 first-batch-junit.xml；后续各票保留自己的结果。记录中的 fixture 与 synthetic 人工身份均不是业务事实。未执行的宿主触发、真实 WiFi/构建、外部 ACL、完整恢复、代码门禁和索引功能按各票保持待验。
