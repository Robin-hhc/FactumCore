# 治理资产入口

本目录维护 Schema、受控枚举、契约适配、模板、规范与来源锁；导航见 [index.md](index.md)。正式技术结论只进入 `../knowledge/`，原件只进入 `../docs-raw/`，系统设计和 SDD 在 `../docs-llm-wiki/`。

已有规则字节由 `framework.lock.yaml` 固定。修改受锁定资产时同步审查版本与摘要，不以 Schema 通过替代事实核验。`sources.lock.yaml` 当前是空登记，不表示已经捕获来源。

本目录位于 `aiotbot-knowledge/wifi/governance/`；领域相对规则路径随根迁移保持不变。现存 1.0 声明资产和契约适配保留其参考身份，所依赖旧程序已归档，不能据文件存在宣称治理门禁可运行。纯目录迁移不改受锁定规则字节或重签证明。

共享执行能力归独立能力仓的 `hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query`，由 `hs-workspace-explore` 定位项目；FactumCore 不保留旧 Skill/Workflow 占位。能力仓根、URL、版本和安装状态未知，后续按受信版本接入，不从来源内容加载程序。本轮只同步目录和设计，既有 SDD 原字节保留，开发前再重新基线。纯文档确认免代码 lint 与代码本地/合入只读双门禁的边界遵循领域 AGENTS。
