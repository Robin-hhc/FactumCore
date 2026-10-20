# AIoTBot 当前设计与 SDD 入口

本目录是 `aiotbot-knowledge-wifi/docs-llm-wiki/`，平铺保留 `AGENTS.md`、`README.md`、`AIoTBot知识库架构设计.md`、`知识库详细设计.md`、`task.md`，以及既有 `sdd/`。先按任务选择入口，避免全量加载文档。

| 任务 | 阅读入口 |
|---|---|
| 当前范围与状态 | [README.md](README.md) |
| 总体架构、目录职责和三条链路 | [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) |
| 逐文件开发要求、阶段接口与验收 | [知识库详细设计.md](知识库详细设计.md) |
| 当前模块任务与推进顺序 | [task.md](task.md)，先列模块、依赖与完成条件，后续再拆 SDD 任务 |
| 后续开发 | [SDD 入口](sdd/knowledge-v1/README.md)，设计定稿后先重新建立基线，再依次看需求、模块设计、ticket 和验收记录 |

所有现行名称与路径以《AIoTBot知识库架构设计》§5.3 目录树为准，用户后续明确决定优先。本次只建设根下的 `aiotbot-knowledge-wifi/`，无中间目录或其他领域目录；`main/` 为空。四个 Skill 使用 `hs-workspace-explore`、`hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query` 名称，连同生产、治理 Workflow 在独立能力仓实现。能力仓根、URL、版本和安装状态未提供，保持 unknown，FactumCore 不保留旧占位。架构和链路图沿用原结构；明显设计冲突先讨论。Schema/Contract 的领域机器规则归[治理目录](../governance/)，此处不另造执行契约。

本轮只同步目录骨架与设计，不开发程序、不调整 SDD 任务状态。现存 SDD 原字节保留，旧名称、路径和 verified 保持当时身份；设计定稿后再重新基线并按批准任务开发。旧实现归档见[历史布局记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)，当前不可按历史 CLI 手册运行。纯文档真人确认免代码 lint、代码双只读门禁、五类 raw 范围与未知业务上下文遵循仓根及领域 AGENTS；普通文档整理不读取受限 gold。

旧研究、实验、历史方案和旧 Agent 约定已移到 Git 仓外。归档身份见 [本次整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)；当前目录不再建立 research/experiments/agents/superpowers/workflows 或设计文档子目录。新增系统设计优先补现有两份主文档；实现规格和实际记录放入相应 SDD 工件。

本轮迁移同步活跃入口和详设，既有 SDD 的来源摘要、路径和记录不作批量替换；重新基线时显式记录新旧关系，不把路径整理当成新业务验收。
