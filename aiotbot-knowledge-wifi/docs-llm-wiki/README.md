# AIoTBot 设计与开发

当前文档采用设计、模块任务与入口文件平铺加 `sdd/` 的布局，不再保留设计文档子目录。总体设计与用户明确修正是当前依据；详细设计细化文件、接口、三条链路和验收要求。

| 文件 / 目录 | 职责 |
|---|---|
| [AGENTS.md](AGENTS.md) | Agent 阅读入口、维护边界与修改落点 |
| [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) | 当前总体设计，重点是 §5.3 目录架构及第 11 章知识库架构与链路 |
| [知识库详细设计.md](知识库详细设计.md) | 目录展开、逐文件开发要求、阶段接口、三链路及验收 |
| [task.md](task.md) | 当前模块任务、依赖、完成条件与建议推进顺序；后续再拆 SDD 任务 |
| [sdd/knowledge-v1/](sdd/knowledge-v1/README.md) | 既有需求、模块、任务、追踪与历史验收记录；设计定稿后再重新对齐 |

FactumCore 承载业务代码与 WiFi 知识，目录以主设计 §5.3 目录树为准：`main/` 保持空目录；唯一领域根为 `aiotbot-knowledge-wifi/`，直接位于仓根，无中间目录或其他领域目录。本目录为 `aiotbot-knowledge-wifi/docs-llm-wiki/`，承载系统设计与既有 SDD，不存放正式业务知识卡。

四个共享 Skill 使用 `hs-workspace-explore`、`hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query` 名称，与生产、治理 Workflow 在独立能力仓实现，保留其 `skills/common/knowledge/` 与 `workflows/common/knowledge/` 归属。FactumCore 已移除六个旧占位；能力仓根、URL、版本和安装状态尚未提供，不假定可以调用。

当前阶段只完善设计文档。《知识库详细设计》按 §5.3 展开具体文件、接口、生产/治理/消费三条链路，并参考 OpenFlow 的 Workflow 模板格式；这些是目标设计，尚未创建运行程序或安装模板。本轮保留现有 SDD，不重置任务状态；后续先重新建立设计基线和任务映射，再实施开发。

首版覆盖 chip12/chip08/chip07c 的 Host/Device 六逻辑 Target。文档只处理五类 raw 目录内已落地原件，真人确认后 stable；代码相关卡本地通过后 stable，上库按最新业务代码只读二次检查。业务路径、构建和版本未登记时保留 unknown。

T01/T02 及 raw 捕获 → 候选 → 真人确认 → stable 事务曾完成合成机制验证，相关实现、工具和依赖已归档仓外。当前 checkout 不提供可运行 CLI，历史 230 项合成测试不代表当前部署可用。[历史布局记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)、`traceability.json.current_deployment`、[任务入口](sdd/knowledge-v1/tasks.md)和[验收记录](sdd/knowledge-v1/records/README.md)保留原版本身份，其中的旧路径不作为当前落点。[raw 手工操作说明](sdd/knowledge-v1/document-chain-usage.md)仅供历史接口参考。

旧研究、实验及历史方案已移至仓外归档，用户删除的六份旧稿不恢复；归档与迁移证据见 [整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)。SDD 保留当前需求、设计、任务、测试与历史验收身份，文档清理不改写已有成绩。
