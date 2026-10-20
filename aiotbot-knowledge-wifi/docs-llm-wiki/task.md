# WiFi节点能力开发任务

日期：2026-10-21。用户已批准按18节点Skill+两个Workflow完成SDD与开发，当前依据[详设v4](知识库详细设计.md)和[knowledge-v2](sdd/knowledge-v2/README.md)。T201–T210已完成开发及隔离机制验收；T211真实外部验收仍pending，不继承knowledge-v1的历史通过状态。

只做根下aiotbot-knowledge-wifi，main保持空；四个旧聚合Skill不再作为开发分组，hs-knowledge-ingest/hs-knowledge-lint仅是Workflow。节点包、Workflow、领域规则、资产和验收均在FactumCore；使用当前远端，本机安装位置不写进公共config。

| 当前票 | 交付 | 依赖 | 状态 |
|---|---|---|---|
| [T201](sdd/knowledge-v2/tickets/T201.md) | 契约与运行协议 | 无 | complete |
| [T202](sdd/knowledge-v2/tickets/T202.md) | 发现与项目绑定 | T201 | complete |
| [T203](sdd/knowledge-v2/tickets/T203.md) | raw捕获与可恢复快照 | T202 | complete |
| [T204](sdd/knowledge-v2/tickets/T204.md) | 六决策候选与精确视图 | T203 | complete |
| [T205](sdd/knowledge-v2/tickets/T205.md) | 真实动作、事务与恢复 | T204 | complete |
| [T206](sdd/knowledge-v2/tickets/T206.md) | 索引、查询与回归激活 | T205 | complete |
| [T207](sdd/knowledge-v2/tickets/T207.md) | 维护事件与双水位 | T203, T205, T206 | complete |
| [T208](sdd/knowledge-v2/tickets/T208.md) | 代码捕获与只读双门禁 | T202, T204, T205 | complete |
| [T209](sdd/knowledge-v2/tickets/T209.md) | 两个Workflow和节点包 | T202, T203, T204, T205, T206, T207, T208 | complete |
| [T210](sdd/knowledge-v2/tickets/T210.md) | 单仓跨节点集成与开发交付 | T201, T202, T203, T204, T205, T206, T207, T208, T209 | complete |
| [T211](sdd/knowledge-v2/tickets/T211.md) | 真实外部环境验收 | T210 | pending |

## 节点清单与推进顺序

- `hs-workspace-explore`：绑定项目（T202）。
- `hs-knowledge-source-capture`：固定来源（T203）。
- `hs-knowledge-change-plan`：六决策计划（T204）。
- `hs-knowledge-view-materialize`：物化最终视图（T204）。
- `hs-knowledge-governance-handoff`：移交治理（T204）。
- `hs-knowledge-candidate-inspect`：检查候选身份（T205）。
- `hs-knowledge-confirmation-prepare`：准备真人展示（T205）。
- `hs-knowledge-confirmation-record`：记录真实动作（T205）。
- `hs-knowledge-local-check`：代码本地核验（T208）。
- `hs-knowledge-candidate-revise`：修订或缩窄（T204）。
- `hs-knowledge-apply`：精确事务落位（T205）。
- `hs-knowledge-recover`：恢复事务（T205）。
- `hs-knowledge-index-build`：构建验证和激活索引（T206）。
- `hs-knowledge-query-regression`：回归候选代（T206）。
- `hs-knowledge-publish-handoff`：移交发布（T209）。
- `hs-knowledge-merge-check`：最新代码合入复验（T208）。
- `hs-knowledge-maintain`：维护与阻断复核（T207）。
- `hs-knowledge-query`：消费知识（T206）。

先完成契约→发现→五raw→六决策视图→真人确认与恢复事务→local索引消费，再按依赖补维护/代码门禁、Workflow及单仓跨节点集成。shared代码卡另需真实merge证明；纯文档不额外执行代码lint。

每票按失败测试→实现→针对验证/回归→独立审查→范围提交/实际发布推进，证据到位后再更新状态。M01–M09仅在v2模块表用作责任索引，历史v1状态不变。

## 验收边界

- 首发只接受conventions/chips/storys/specs/protocols已落地raw；网页、sources链接、仓外映射与3ms延期。
- 真实人确认确切最终字节；user Gate不变成Skill，未签名/Agent/无动作/陈旧/部分接受不apply。
- 所有卡metadata受Claim资格约束；过滤后重算全局topK，同代read/receipt，输出前复查撤销。
- 批次逐项终态完整；受控只读Git禁外部执行；代码检查只读且需正向证据。
- T211真实人/宿主触发/六Target三pair/真实CI合入/外部权限分别留证；缺输入保持pending，不能用合成测试关闭。

当前验收：[实际结果](sdd/knowledge-v2/records/development-acceptance-20261021.json)；共200个唯一用例，199通过、1跳过。原件/确认/代码等测试材料为隔离合成输入，真实宿主与六Target不据此关闭。
