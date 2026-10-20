# AIoTBot 当前设计与 SDD 入口

本目录是 `aiot-wifi-knowledge/docs-llm-wiki/`，只保留四个根文件和当前 SDD：`AGENTS.md`、`README.md`、`AIoTBot知识库架构设计.md`、`知识库详细设计.md`，以及 `sdd/`。先按任务选择入口，避免全量加载文档。

| 任务 | 阅读入口 |
|---|---|
| 当前范围与状态 | [README.md](README.md) |
| 总体架构、目录职责和三条链路 | [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) |
| 逐文件开发要求、阶段接口与验收 | [知识库详细设计.md](知识库详细设计.md) |
| 开发实现 | [SDD 入口](sdd/knowledge-v1/README.md)，依次看需求、模块设计、当前 ticket 和验收记录 |

所有现行名称与路径以《AIoTBot知识库架构设计》§5.3 目录树为准；其他章节、详设和 SDD 不另起别名或中间目录。用户后续明确决定优先。FactumCore 仅保留 WiFi 领域；`main/` 为空，四个 Skill 和两个 Workflow 为目录骨架。架构和链路图沿用原结构，只按已确认范围增补；明显设计冲突先讨论。Schema/Contract 的机器规则归[领域治理目录](../governance/)，此处不另造执行契约。

开发按批准 SDD 实施，保留真实状态和证据边界。现有执行程序、工具和依赖已归档；当前 checkout 不可按历史 CLI 手册运行。先读[布局与部署记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)和 `traceability.json.current_deployment`，历史 verified 不代表当前部署。纯文档确认、代码双门禁、当前 raw 范围与未知业务上下文遵循仓根及领域 AGENTS；普通文档整理不读取受限 gold。

旧研究、实验、历史方案和旧 Agent 约定已移到 Git 仓外。归档身份见 [本次整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)；当前目录不再建立 research/experiments/agents/superpowers/workflows 或设计文档子目录。新增系统设计优先补现有两份主文档；实现规格和实际记录放入相应 SDD 工件。

迁移或改名后，同步根入口、相对链接、受控设计路径及 SDD 当前来源摘要；历史记录保留原身份，不把路径整理当成新业务验收。
