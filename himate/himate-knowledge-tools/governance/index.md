# 治理规则导航

- [卡片规范](specs/cards.md)：卡ID、文档/代码引用、定位与知识表达。
- [生命周期](specs/lifecycle.md)：六决策及正式卡去向。
- [固定CI](specs/ci-runner.md)：只读检查边界。
- schemas：格式规则；templates：主题模板；contracts：业务算法。
- `framework.lock.yaml` 固定共享框架版本和摘要。各知识根的 `governance/sources.lock.yaml` 记录本库的来源身份与处理信息。

执行流程见领域知识仓的 `docs-llm-wiki/知识库详细设计.md`，工作流定义在工具包的 [workflows/](../workflows/)。
