# AIoTBot 设计与开发

当前文档采用设计、模块任务与入口文件平铺加 `sdd/` 的布局，不再保留设计文档子目录。总体设计与用户明确修正是当前依据；详细设计细化文件、接口、三条链路和验收要求。

| 文件 / 目录 | 职责 |
|---|---|
| [AGENTS.md](AGENTS.md) | Agent 阅读入口、维护边界与修改落点 |
| [AIoTBot知识库架构设计.md](AIoTBot知识库架构设计.md) | 当前总体设计，重点是 §5.3 目录架构及第 11 章知识库架构与链路 |
| [知识库详细设计.md](知识库详细设计.md) | 目录展开、逐文件开发要求、阶段接口、三链路及验收 |
| [task.md](task.md) | 当前节点化票据、依赖、完成条件与推进顺序 |
| [使用说明.md](使用说明.md) | 环境准备、初始化安装、合成 Demo、真实 raw 生产与治理、索引查询、更新恢复及排错 |
| [sdd/knowledge-v2/](sdd/knowledge-v2/README.md) | 当前节点化需求、设计、T201–T211任务与验收 |
| [sdd/knowledge-v1/](sdd/knowledge-v1/README.md) | 原字节保留的历史需求、任务和验收身份，不继承成绩 |

FactumCore 承载业务代码与 WiFi 知识，目录以主设计 §5.3 目录树为准：`main/` 保持空目录；唯一领域根为 `aiotbot-knowledge-wifi-mp/`，直接位于仓根，无中间目录或其他领域目录。本目录为 `aiotbot-knowledge-wifi-mp/docs-llm-wiki/`，承载系统设计与既有 SDD，不存放正式业务知识卡。

18个节点Skill（完整清单见详设v4），与hs-knowledge-ingest、hs-knowledge-lint两个Workflow 在本仓能力目录实现，保留其 `skills/common/knowledge/` 与 `workflows/common/knowledge/` 归属。原四聚合Skill已拆为18节点包；能力在FactumCore根目录开发/发布，实际包版本与安装状态以当前验收记录为准。

当前按详设v4与knowledge-v2实施节点化SDD开发；18个Skill和两个Workflow逐票交付，不把规划文件当运行成功。能力在本仓根skills/和workflows/开发，与main同级；发行和安装身份按实际记录，个人路径不写入公开配置。knowledge-v1只保留历史，不重置其任务状态。

当前详设为v4.1，T201–T210开发已完成。见[实际验收](sdd/knowledge-v2/records/development-acceptance-20261021.json)、[源码身份](sdd/knowledge-v2/records/implementation-manifest.json)和[发布](sdd/knowledge-v2/records/publication-20261021.md)；T211真实外部环境仍pending。

首版覆盖 chip12/chip08/chip07c 的 Host/Device 六逻辑 Target。文档只处理五类 raw 目录内已落地原件，真人确认后 stable；代码相关卡本地通过后 stable，上库按最新业务代码只读二次检查。业务路径、构建和版本未登记时保留 unknown。

T01/T02 及 raw 捕获 → 候选 → 真人确认 → stable 事务曾完成合成机制验证，相关实现、工具和依赖已归档仓外。当前节点是否可运行按knowledge-v2记录核实；历史230项合成测试不代表当前部署可用。[历史布局记录](sdd/knowledge-v1/records/workspace-layout-20261020.md)、`traceability.json.current_deployment`、[任务入口](sdd/knowledge-v1/tasks.md)和[验收记录](sdd/knowledge-v1/records/README.md)保留原版本身份，其中的旧路径不作为当前落点。[raw 手工操作说明](sdd/knowledge-v1/document-chain-usage.md)仅供历史接口参考。

旧研究、实验及历史方案已移至仓外归档，用户删除的六份旧稿不恢复；归档与迁移证据见 [整理记录](sdd/knowledge-v1/records/docs-layout-20261020.md)。SDD 保留当前需求、设计、任务、测试与历史验收身份，文档清理不改写已有成绩。
