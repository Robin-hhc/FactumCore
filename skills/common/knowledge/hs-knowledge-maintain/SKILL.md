---
name: hs-knowledge-maintain
description: 按明确请求审计知识库代码引用、登记来源事件或维护已解决的来源限制。
---

# 独立引用审计与来源维护

仅处理明确的维护任务。在已确认的数据所在知识根 K 调用仓内 CLI，读取实际结果和引用。

- 生成只读代码引用报告：读[引用审计](references/audit.md)，调用 `knowledge maintain --action audit-references`。
- 观察限制、登记或恢复来源事件、复验并解除已解决的机械限制：读[事件与限制](references/request.md)，只执行对应动作。

引用报告交付实际 `report_ref`、统计和缺口；事件动作交付真实状态及未解决项。事件登记与 `advance` 有正式写入效果，只按明确请求执行，不以字节相同证明技术正确或解除语义限制。

日常增量治理使用 `hs-knowledge-lint` Workflow；同步、待办、索引修复和完成核验各有独立 Skill。本 Skill 不承接这些节点，也不成稿、审阅或发布知识。执行入口不明时交 explore 定位。
