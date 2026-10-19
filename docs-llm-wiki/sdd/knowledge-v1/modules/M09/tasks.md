# M09 Skills/Workflow与部署验收：实施任务

| Ticket | 行为 | Blocked by |
|---|---|---|
| [T20](../../tickets/T20.md) | 生产 Skill/Workflow 与代码/raw 两条入口编排 | T02, T04, T08, T09 |
| [T21](../../tickets/T21.md) | 治理 Workflow、本地与可信 CI 接线 | T13, T16, T20 |
| [T22](../../tickets/T22.md) | 消费 Skill 与上下文、回源、输出前复查 | T02, T12, T17 |
| [T23](../../tickets/T23.md) | 框架挂载、用户级托管规则与 Windows 运维 | T19, T20, T21, T22 |
| [T24](../../tickets/T24.md) | 目标宿主仓外隐式触发实测（外部条件验证） | T23 |
| [T25](../../tickets/T25.md) | 六 Target/三 pair 的真实工程逐槽接入（外部条件验证） | T23 |
| [T26](../../tickets/T26.md) | 组隔离与撤销的真实负测（外部条件验证） | T23 |
| [T27](../../tickets/T27.md) | 汇总可重复合成验收与失败定位 | T19, T21, T22 |
| [T28](../../tickets/T28.md) | 首发交付证据、三链路回归与状态结案 | T24, T25, T26, T27 |

逐 ticket 执行 red→green→review→record。当前批次状态见 ../../tasks.md；只有已落地且验证的行为才可关闭对应要求。
