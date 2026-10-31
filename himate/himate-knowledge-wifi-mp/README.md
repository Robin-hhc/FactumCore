# HiMate WiFi Knowledge

HiMate 将设计文档、规格和代码分析蒸馏为可追溯知识卡，通过来源 ID 和具体定位关联原文与实现，供 Agent 在开发和问题定位时检索使用。

| 任务 | 入口 |
|---|---|
| 处理新增、修改或删除的文档 | `hs-knowledge-ingest` Workflow |
| 巡检原件和已引用代码的变化 | `hs-knowledge-lint` Workflow |
| 精确检索、精读卡片及追溯来源 | `hs-knowledge-query` Skill |

知识根由项目 `config.yml` 选择，默认位于 `repo/himate/himate-knowledge-wifi-mp/`。首次部署安装运行依赖、Skill 和 Workflow；日常将文档放入 `docs-raw/`，在 OpenFlow 运行入库工作流，再使用 Query Skill 提问。

[使用说明](docs-llm-wiki/使用说明.md)介绍部署和 OpenFlow 日常操作；[运维与命令参考](docs-llm-wiki/运维与命令参考.md)提供环境准备及手动命令；[详细设计](docs-llm-wiki/知识库详细设计.md)说明入库、巡检及检索；[架构设计](docs-llm-wiki/HiMate知识库架构设计.md#53-himate-knowledge目录架构)说明组件与目录分工。开发者从[开发指南](CONTRIBUTING.md)进入。

原件在 `docs-raw/`，正式卡在 `knowledge/`，来源身份和处理版本保存在 `governance/sources.lock.yaml`。`.build/` 保存当前任务的材料与候选；`artifacts/` 保存派生数据库、运行回执和阅读产物，也可存放独立维护的本地模型，不能整目录清空。更新与清理边界见[架构设计 §5.5](docs-llm-wiki/HiMate知识库架构设计.md#55-框架更新与目录清理)。
