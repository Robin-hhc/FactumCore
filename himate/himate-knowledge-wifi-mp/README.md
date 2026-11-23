# HiMate WiFi Knowledge

HiMate 将设计文档、规格和代码分析蒸馏为可追溯知识卡，供 Agent 在开发和问题定位时检索使用。

参照使用指南部署能力包 `himate-skills`，在 OpenFlow 知识库页校验目录、检查并补齐执行端的环境，再保存绑定。文件上传后可直接启动入库，发布后即可查阅正式知识。[使用指南](docs-llm-wiki/HiMate知识库使用指南.md)

| 任务 | 入口 |
|---|---|
| 检查 CLI 和 Python 依赖 | OpenFlow 知识库页的「环境检查」 |
| 将文件按分类保存到原始资料 | OpenFlow 知识库页的「文件上传」 |
| 入库刚上传的文件 | 完成弹窗或「上传记录」里的「开始入库」 |
| 手动处理其他新增、修改或删除的文档 | `hs-knowledge-ingest` Workflow |
| 巡检原件和已引用代码的变化 | `hs-knowledge-lint` Workflow |
| 检索、精读卡片及追溯来源 | `hs-knowledge-query` Skill |

本目录是知识根，随业务维护 `AGENTS.md`、`config.yml`、原件、来源登记和正式卡。默认布局为 `repo/himate/himate-knowledge-wifi-mp/`，`repo/` 是可包含多个代码仓的 manifest 工作区根。

架构、详细流程和日常操作见[设计与使用文档](docs-llm-wiki/README.md)。
