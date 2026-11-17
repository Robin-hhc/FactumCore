# 治理规则导航

- [卡片规范](specs/cards.md)：卡ID、文档/代码引用、定位与知识表达。
- [生命周期](specs/lifecycle.md)：六决策及正式卡去向。
- [固定CI](specs/ci-runner.md)：只读检查边界。
- [Schema](schemas/)定义机器可校验的格式，[业务算法](contracts/)由 CLI 执行。[导航模板](templates/index.md)供人工维护索引。
- `framework.lock.yaml` 固定共享框架版本和摘要。各知识根的 `governance/sources.lock.yaml` 记录本库的来源身份与处理信息。

执行流程见领域知识仓的 `docs-llm-wiki/知识库详细设计.md`。工作流由 `himate-skills` 发布，知识卡模板随 `hs-knowledge-view-materialize` 安装。
