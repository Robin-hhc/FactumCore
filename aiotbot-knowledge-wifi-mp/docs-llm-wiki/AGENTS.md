# AIoTBot 当前设计与 SDD 入口

本目录是 `aiotbot-knowledge-wifi-mp/docs-llm-wiki/`，平铺保留 `AGENTS.md`、`README.md`、`AIoTBot知识库架构设计.md`、`知识库详细设计.md`、`task.md`、`使用说明.md`，以及既有 `sdd/`。先按任务选择入口，避免全量加载文档。

| 任务 | 阅读入口 |
|---|---|
| 当前范围与状态 | [README.md](README.md) |
| 总体架构、目录职责和三条链路 | [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) |
| 逐文件开发要求、阶段接口与验收 | [知识库详细设计.md](知识库详细设计.md) |
| 当前模块任务与推进顺序 | [task.md](task.md)，当前T201–T211票据、依赖与完成条件 |
| 初始化、使用教学与排错 | [使用说明.md](使用说明.md)，区分可运行合成 Demo 与待宿主适配的真实确认流程 |
| 后续开发 | [knowledge-v2入口](sdd/knowledge-v2/README.md)，依次看需求、设计、ticket和实际记录；v1仅历史参考 |

所有现行名称与路径以《AIoTBot知识库架构设计》§5.3 目录树为准，用户后续明确决定优先。本次只建设根下的 `aiotbot-knowledge-wifi-mp/`，无中间目录或其他领域目录；`main/` 为空。18个节点Skill（见详设v4清单），连同hs-knowledge-ingest、hs-knowledge-lint两个Workflow 在本仓能力目录实现。能力在FactumCore根目录开发，发行/安装状态按实际记录，不推断已有可用包，FactumCore只建立批准的节点包和两个Workflow。架构和链路图沿用原结构；明显设计冲突先讨论。Schema/Contract 的领域机器规则归[治理目录](../governance/)，此处不另造执行契约。

本轮已批准按knowledge-v2进行SDD与开发，新票初始pending，实际验证后更新。knowledge-v1原字节保留，旧名称、路径和verified保持当时身份，不沿用作新实现证明。旧实现归档见[历史布局记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)，当前不可按历史 CLI 手册运行。纯文档真人确认免代码 lint、代码双只读门禁、五类 raw 范围与未知业务上下文遵循仓根及领域 AGENTS；普通文档整理不读取受限 gold。

旧研究、实验、历史方案和旧 Agent 约定已移到 Git 仓外。归档身份见 [本次整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)；当前目录不再建立 research/experiments/agents/superpowers/workflows 或设计文档子目录。新增系统设计优先补现有两份主文档；实现规格和实际记录放入相应 SDD 工件。

当前基线与任务在knowledge-v2，旧knowledge-v1的来源摘要、路径和记录不作批量替换；新旧关系显式记录，不把规划或路径整理当功能验收。
