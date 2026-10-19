# M05 人工确认与事务：实施任务

| Ticket | 行为 | Blocked by |
|---|---|---|
| [T06](../../tickets/T06.md) | 人工文档确认与部分接受重确认 | T05 |
| [T07](../../tickets/T07.md) | 文档 stable 事务落位与全域唯一性 | T06 |
| [T08](../../tickets/T08.md) | apply 中断、后续编辑与阶段恢复 | T07 |
| [T09](../../tickets/T09.md) | 文档更新与跨卡 merge/split/deprecate 完整闭环 | T07 |
| [T13](../../tickets/T13.md) | 代码本地证据义务到 stable/local 的闭环 | T04, T05, T08, T09, T10 |
| [T16](../../tickets/T16.md) | 实际合入身份、混合提交与 shared 发布 | T10, T15 |
| [T18](../../tickets/T18.md) | 复核恢复与双水位协调 | T16, T17 |

逐 ticket 执行 red→green→review→record。当前批次状态见 ../../tasks.md；只有已落地且验证的行为才可关闭对应要求。
