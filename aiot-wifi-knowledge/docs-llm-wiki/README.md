# AIoTBot 设计与开发

当前文档采用四个平铺文件加 `sdd/` 的布局，不再保留设计文档子目录。总体设计与用户明确修正是当前依据；详细设计细化文件、接口、三条链路和验收要求。

| 文件 / 目录 | 职责 |
|---|---|
| [AGENTS.md](AGENTS.md) | Agent 阅读入口、维护边界与修改落点 |
| [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) | 当前总体设计，重点是 §5.3 目录架构及第 11 章知识库架构与链路 |
| [知识库详细设计.md](知识库详细设计.md) | 目录展开、逐文件开发要求、阶段接口、三链路及验收 |
| [sdd/knowledge-v1/](sdd/knowledge-v1/README.md) | 18 需求、9 模块、28 任务、148 路径与 E01–E34 追踪，以及实际验收记录 |

当前在 FactumCore 单仓开发，目录以主设计 §5.3 为准：`main/` 保持空目录，`skills/` 与 `workflows/` 仅保留指定入口的空骨架，领域仅保留 `aiot-wifi-knowledge/`。本目录位于该领域根内的 `docs-llm-wiki/`，承载系统设计与 SDD，不存放正式业务知识卡。

首版覆盖 chip12/chip08/chip07c 的 Host/Device 六逻辑 Target。文档只处理五类 raw 目录内已落地原件，真人确认后 stable；代码相关卡本地通过后 stable，上库按最新业务代码只读二次检查。业务路径、构建和版本未登记时保留 unknown。

T01/T02 及 raw 捕获 → 候选 → 真人确认 → stable 事务曾完成合成机制验证，相关实现、工具和依赖已按本次布局要求移到仓外。当前 checkout 不提供可运行 CLI，历史 230 项合成测试不代表当前部署可用。当前状态见[布局与部署记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)及 `traceability.json.current_deployment`；[任务入口](sdd/knowledge-v1/tasks.md)和[验收记录](sdd/knowledge-v1/records/README.md)保留历史开发身份。[raw 手工操作说明](sdd/knowledge-v1/document-chain-usage.md)仅供历史接口参考。

旧研究、实验及历史方案已移至仓外归档，用户删除的六份旧稿不恢复；归档与迁移证据见 [整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)。SDD 保留当前需求、设计、任务、测试与历史验收身份，文档清理不改写已有成绩。
