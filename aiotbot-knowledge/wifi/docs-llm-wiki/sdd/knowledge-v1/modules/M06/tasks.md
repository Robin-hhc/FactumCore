# M06 代码双门禁：实施任务

| Ticket | 行为 | Blocked by |
|---|---|---|
| [T13](../../tickets/T13.md) | 代码本地证据义务到 stable/local 的闭环 | T04, T05, T08, T09, T10 |
| [T14](../../tickets/T14.md) | 最新源码向量上的只读 merge gate | T13 |
| [T15](../../tickets/T15.md) | 证明复用、依赖继承、重验与过期重核 | T14 |
| [T16](../../tickets/T16.md) | 实际合入身份、混合提交与 shared 发布 | T10, T15 |
| [T18](../../tickets/T18.md) | 复核恢复与双水位协调 | T16, T17 |
| [T21](../../tickets/T21.md) | 治理 Workflow、本地与可信 CI 接线 | T13, T16, T20 |
| [T25](../../tickets/T25.md) | 六 Target/三 pair 的真实工程逐槽接入（外部条件验证） | T23 |

逐 ticket 执行 red→green→review→record。当前批次状态见 ../../tasks.md；只有已落地且验证的行为才可关闭对应要求。
