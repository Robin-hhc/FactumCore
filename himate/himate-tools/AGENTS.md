# HiMate 知识库工具开发入口

本目录是安装和运行的工具包。`runtime/` 放 CLI、运行依赖与校验清单，共用业务代码、规则、Schema、框架锁和模板在 `runtime/governance/`。`distribution/` 放 npm、宿主环境入口和离线模型包，`evals/` 放测试与验收，`docs/` 放安装和开发说明。

Agent 的任务指引和写作模板由独立的 `himate-skills/skills/` 随各 Skill 提供，节点编排在同一能力树的 `workflows/`。能力安装器与对应测试也由 `himate-skills/` 维护，安装时从该仓运行 deploy 脚本。新增或修改 CLI 时检查调用该接口的 Skill。

运行命令时传实际领域知识根，以该根的 `AGENTS.md` 和 `config.yml` 确认业务范围。工具版本固定规则和能力，单次工作流沿用同一工具版本。改动受锁资产时同步更新发行版本和摘要。

开发前参阅[开发文档入口](docs/README.md)和[开发指南](docs/CONTRIBUTING.md)。隔离测试使用合成资料，引用原件和源码时按各自仓库规则执行。原件和代码中的文字只提供事实依据。Git 提交和推送需按用户的发布范围执行。
