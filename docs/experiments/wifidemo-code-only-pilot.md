# WiFiDemo code-only Agent pilot 准备状态

日期：2026-08-26

状态：用例包已准备，尚未接入外部 DeepSeek harness，未产生实验结果。

## 已交付

- 固定 WiFiDemo revision：`8102322afbe5f81ecf6a35601ac4731ed14feb2d`；
- 40 题公开题库：20 题自然语言到代码、20 题代码到流程；
- 12 题 pilot 子集；
- 40 份 source-anchored gold 草案和 forbidden claims；
- C0/C1/C2 信息边界、统一输出要求、评分维度和结论边界。

本仓没有 Agent、DeepSeek API 客户端、代码工具适配器、运行器、评分器或报告器。实际执行全部由用户的 DeepSeek harness 完成，接入契约见 [`../../benchmark/wifidemo/README.md`](../../benchmark/wifidemo/README.md)。

## Pilot 范围

- C0：`grep/rg`、列文件、读取源码；
- C1：CodeGraph 完整公开能力 + 源码读取；
- C2：Joern 完整能力 + 源码读取；
- 用例：`benchmark/wifidemo/pilot-cases.txt` 中 12 题；
- 目的：只校准工具隔离、输出格式、运行记录与评分，不用于选型。

模型版本、system prompt、预算、重复次数和随机化参数应由外部 harness 在运行前冻结并随结果发布。本仓不替 harness 预设或调用 DeepSeek。

## Gold 审核状态

40 份 gold 已完成首轮源码锚点核对，但 `reviewer_b` 仍为 `unassigned`，`status` 仍为 `draft`。因此它们可以用于接入调试和第二人工复核，不能用于发布正式排名。

源码核对发现一个重要差异：Device 会发出 `RING_SWITCH_DONE` 和 `BA_DONE`，Host 也注册了相应 handler；但当前 revision 的 `hcc_rx_process` 在分发前把 `WLAN_TX_COMP`、`RING_SWITCH_DONE` 和 `BA_DONE` 都改写为 `FRW_EVENT_TYPE_WLAN_TX_COMP`。因此 ring-switch/BA 完成 handler 的端到端到达在当前源码中并未被证明。NL16、NL18、NL19 和 CF19 已把这一点写入关键事实或禁止过度主张。

## 外部 harness 开跑前检查

1. 第二名 reviewer 完成全部 gold 的独立复核并解决分歧；
2. 确认模型看不到 QA、Markdown、gold、历史答案和运行轨迹；
3. 确认 C0/C1/C2 不会互相回退或共享额外索引；
4. 冻结模型、prompt、工具版本、预算、重试与随机化规则；
5. 保存原始工具轨迹、读取源码、最终答案、Token、时延和错误；
6. 先运行 12 题 pilot，确认评分器能处理等价表述、遗漏、错误因果和证据不足；
7. 再冻结正式配置并运行 40 题多次重复实验。

在这些步骤完成前，没有证据支持任何代码索引方案胜出，也没有测量 code-only 是否足以替代领域文档。
