# HiMate WiFi Knowledge

HiMate 将设计文档、规格和代码分析蒸馏为可追溯知识卡，供 Agent 在开发和问题定位时检索使用。

`main` 提供开发内容和空知识库模板。`test` 同步 `main` 的开发版本，保存用于本地测试和 OpenFlow 可视化验收的原件与知识卡。参见[分支约定](docs-raw/index.md#分支约定)。

参照[使用指南](docs-llm-wiki/使用说明.md)部署工具包 `himate-tools` 和能力包 `himate-skills`。在 OpenFlow 知识库页绑定本库并检查环境，再添加原件，运行入库流程后即可查阅正式知识。扫描文档可按需为本库准备离线 OCR 模型。

| 任务 | 入口 |
|---|---|
| 检查 Python 依赖、补装或注册 `knowledge` 命令 | OpenFlow 知识库页的「环境检查」和「安装环境」 |
| 将文件按分类保存到原始资料 | OpenFlow 知识库页的「添加资料」 |
| 处理新增、修改或删除的文档 | `hs-knowledge-ingest` Workflow |
| 巡检原件和已引用代码的变化 | `hs-knowledge-lint` Workflow |
| 检索、精读卡片及追溯来源 | `hs-knowledge-query` Skill |

本目录是知识根，随业务维护 `AGENTS.md`、`config.yml`、原件、来源登记和正式卡。默认布局为 `repo/himate/himate-knowledge-wifi-mp/`，`repo/` 是可包含多个代码仓的 manifest 工作区根。

架构、详细流程和日常操作见[设计与使用文档](docs-llm-wiki/README.md)。
