# HiMate WiFi Knowledge

HiMate 将设计文档、规格和代码分析蒸馏为可追溯知识卡，供 Agent 在开发和问题定位时检索使用。

从[使用说明](docs-llm-wiki/使用说明.md)开始：一次安装完整的 Docling 多格式解析与 OCR 环境，将文档放入 `docs-raw/`，在 OpenFlow 入库和提问。

| 任务 | 入口 |
|---|---|
| 处理新增、修改或删除的文档 | `hs-knowledge-ingest` Workflow |
| 巡检原件和已引用代码的变化 | `hs-knowledge-lint` Workflow |
| 检索、精读卡片及追溯来源 | `hs-knowledge-query` Skill |

本目录是知识根，包含 `AGENTS.md` 和实际配置 `config.yml`。默认布局为 `repo/himate/himate-knowledge-wifi-mp/`，`repo/` 是可包含多个代码仓的 manifest 工作区根。

开发者从[开发指南](CONTRIBUTING.md)进入；组件与数据归属见[架构设计](docs-llm-wiki/HiMate知识库架构设计.md#53-himate-knowledge目录架构)，流程机制见[详细设计](docs-llm-wiki/知识库详细设计.md)。
