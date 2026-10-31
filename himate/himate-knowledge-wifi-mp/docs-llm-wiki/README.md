# HiMate 设计与使用入口

日常从[使用说明](使用说明.md)选择能力。文档用 `repo/` 示意项目根；知识根按项目根 `config.yml` 解析，默认 `repo/himate/himate-knowledge-wifi-mp/`。

| 文档 | 唯一职责 |
|---|---|
| [架构设计](HiMate知识库架构设计.md#53-himate-knowledge目录架构) | 目录、分层及数据归属 |
| [详细设计](知识库详细设计.md) | P1—P5、六决策、巡检与命令职责 |
| [使用说明](使用说明.md) | 部署、放文档、在 OpenFlow 入库和提问 |
| [运维与命令参考](运维与命令参考.md) | 环境准备、CLI、来源管理及故障续办 |
| [知识库关键点](知识库关键点.md) | 领域与来源适配约束 |
| [维护路由](AGENTS.md) | Agent 阅读与维护分工 |

## 业务入口

- 新增、修改、删除文档及修订卡：`hs-knowledge-ingest` Workflow。
- 周期检查 raw 与已登记代码变化：`hs-knowledge-lint` Workflow。
- 搜索和阅读正式知识：`hs-knowledge-query` Skill。
- 独立检查：review Skill；独立来源审计：maintain Skill。

ingest 为 P1 选文件、P2 决策、P3 写卡、P4 独立审阅、P5 入库；lint 的 L1—L4 编排同步、发现、索引维护及汇总，中间复用同一入库流程。

首次使用从使用说明的部署入口开始；维护者按需查运维与命令参考。理解处理逻辑阅读详细设计，确定组件和文件归属阅读架构设计。不同群组按各自知识根和实际访问权限管理材料。
