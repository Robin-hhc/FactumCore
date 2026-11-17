# 共享治理资产入口

本目录维护 Schema、规范、共用业务算法和导航页模板。Agent 写作参考和新卡模板由能力包内的 `hs-knowledge-view-materialize` Skill 提供。每个知识根的 `governance/sources.lock.yaml` 记录本库的来源身份、版本和处理进度。治理资产的入口见 [index.md](index.md)。

`framework.lock.yaml` 固定共享治理字节，`../manifest.json` 固定运行包和框架锁。改动受锁资产时同步更新版本和摘要。锁与 Schema 校验负责机械检查，P4 仍由独立 Agent 审阅知识内容。

新卡字段以[卡片规范](specs/cards.md)为准。业务流程见领域知识仓的 `docs-llm-wiki/HiMate知识库详细设计.md`，测试见[验收入口](../../evals/README.md)。
