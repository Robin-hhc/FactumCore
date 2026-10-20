# AIoTBot 当前设计与 SDD 入口

本目录只保留四个根文件和当前 SDD：`AGENTS.md`、`README.md`、`AIoTBot知识库架构.md`、`知识库详细设计.md`，以及 `sdd/`。先按任务选择入口，避免全量加载文档。

| 任务 | 阅读入口 |
|---|---|
| 当前范围与状态 | [README.md](README.md) |
| 总体架构、目录职责和三条链路 | [AIoTBot知识库架构.md](AIoTBot知识库架构.md) |
| 逐文件开发要求、阶段接口与验收 | [知识库详细设计.md](知识库详细设计.md) |
| 开发实现 | [SDD 入口](sdd/knowledge-v1/README.md)，依次看需求、模块设计、当前 ticket 和验收记录 |

当前主设计及用户后续明确决定优先。架构和链路图沿用原结构，只按已确认范围增补；明显设计冲突先讨论。Schema/Contract 的机器规则仍归仓根 `aiot-wifi-knowledge/governance/`，此处不另造执行契约。

开发按批准 SDD 实施，保留真实状态和证据边界。纯文档确认、代码双门禁、当前 raw 范围与未知业务上下文遵循仓根及领域 AGENTS；普通文档整理不读取受限 gold。

旧研究、实验、历史方案和旧 Agent 约定已移到 Git 仓外。归档身份见 [本次整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)；当前目录不再建立 research/experiments/agents/superpowers/workflows 或设计文档子目录。新增系统设计优先补现有两份主文档；实现规格和实际记录放入相应 SDD 工件。

迁移或改名后，同步根入口、相对链接、受控设计路径及 SDD 当前来源摘要；历史记录保留原身份，不把路径整理当成新业务验收。
