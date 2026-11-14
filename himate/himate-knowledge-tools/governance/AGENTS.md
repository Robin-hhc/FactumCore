# 共享治理资产入口

本目录维护 Schema、模板、规范和共用业务算法。导航见 [index.md](index.md)。每个知识根的 `governance/sources.lock.yaml` 记录本库的来源身份、版本和处理进度。

`framework.lock.yaml` 固定共享治理字节，`../runtime/manifest.json` 固定运行包和框架锁。改动受锁资产时同步更新版本和摘要。锁与 Schema 校验负责机械检查，P4 仍由独立 Agent 审阅知识内容。

新卡字段以[卡片规范](specs/cards.md)为准。业务流程见领域知识仓的 `docs-llm-wiki/知识库详细设计.md`，测试见[验收入口](../evals/README.md)。
