# HiMate WiFi Knowledge

HiMate 将设计文档、规格和代码分析蒸馏为可追溯知识卡，供 Agent 在开发和问题定位时检索使用。

参照[使用说明](docs-llm-wiki/使用说明.md)安装工具并按需为本库准备 OCR，再将文档放入 `docs-raw/`，在 OpenFlow 入库和提问。

| 任务 | 入口 |
|---|---|
| 处理新增、修改或删除的文档 | `hs-knowledge-ingest` Workflow |
| 巡检原件和已引用代码的变化 | `hs-knowledge-lint` Workflow |
| 检索、精读卡片及追溯来源 | `hs-knowledge-query` Skill |

本目录是知识根，包含 `AGENTS.md` 和实际配置 `config.yml`。默认布局为 `repo/himate/himate-knowledge-wifi-mp/`，`repo/` 是可包含多个代码仓的 manifest 工作区根。

架构、详细流程和 WiFi 资料分类见[设计与使用文档](docs-llm-wiki/README.md)。
