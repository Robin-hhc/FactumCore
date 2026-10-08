# 细化设计文档状态与现行入口

更新日期：2026-10-07。

本目录的 01–04 来自此前远端提交，是旧版细化稿，保留原文供追溯，尚未按当前架构同步。其中 `raw0/raw1`、旧卡契约、查询与治理约定，以及“工具功能等价、可随时替换”的表述，不作为当前实施依据。05（落地路线与评测）已于 2026-10-09 自设计文档归档目录并入本目录；架构主文档已由 `docs/架构设计.md` 改名《Wi-Fi 知识库架构设计.md》收口于本目录，原 v0.1 讨论稿同名文件由此取代。

当前 workspace 目录与职责以 [总架构设计（Wi-Fi 知识库架构设计）](Wi-Fi%20知识库架构设计.md) 为准；知识仓的实际能力与操作以 [aiot-knowledge](https://github.com/Robin-hhc/aiot-knowledge) 中的现行入口为准：

- [安装与使用](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/installation_and_usage.md)
- [知识契约](https://github.com/Robin-hhc/aiot-knowledge/blob/main/governance/specs/okf.md)
- [治理与消费流程](https://github.com/Robin-hhc/aiot-knowledge/blob/main/docs/workflows/governance-and-consumption.md)

旧版细化稿：

| 文档 | 当前阅读方式 |
|---|---|
| [01-代码图谱部署](01-代码图谱部署.md) | 历史部署与评测记录；工具覆盖、替换成本及实际效果仍需按试点基线验证 |
| [02-LLM-Wiki构建](02-LLM-Wiki构建.md) | 历史目录、卡片和摄入设计；当前以知识仓现行契约与流程为准 |
| [03-治理机制](03-治理机制.md) | 历史治理设想；已实现检查与待实现自动化按现行入口区分 |
| [04-消费与问答](04-消费与问答.md) | 历史查询与编排设计；当前检索及证据核对按现行消费流程执行 |
| [05-落地路线与评测](05-落地路线与评测.md) | 历史落地路线与依赖清单；阶段划分以《Wi-Fi 知识库架构设计》§1.4 为准 |

本次未取得 01 中 HWDL 评测的原始运行资料，也未复测，不对其历史结果重新判分；不能据此证明工具等价或对所有产品场景普遍有效。
