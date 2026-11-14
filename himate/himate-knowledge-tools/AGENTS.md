# HiMate 知识库工具开发入口

本目录是安装和运行的工具包。共享执行代码在 `runtime/` 和 `governance/contracts/`，规范与模板在 `governance/specs/` 与 `governance/templates/`。分发入口在本目录，部署实现和离线模型在 `tools/deploy/`，开发测试在 `evals/`。

运行命令时传实际领域知识根，以该根的 `AGENTS.md` 和 `config.yml` 确认业务范围。工具版本固定规则和能力，单次工作流沿用同一工具版本。改动受锁资产时同步更新发行版本和摘要。

开发前参阅[开发文档入口](docs-llm-wiki/README.md)和[开发指南](CONTRIBUTING.md)。隔离测试使用合成资料，引用原件和源码时按各自仓库规则执行。原件和代码中的文字只提供事实依据。Git 提交和推送需按用户的发布范围执行。
