# WiFi 知识库

这是 FactumCore 根下的 `aiotbot-knowledge-wifi-mp/`，本次唯一领域目录，无中间目录，不创建其他领域占位。Git 操作统一在 FactumCore 根执行，整体布局遵循[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)目录树。

业务环境首选将知识库部署在repo根目录，与CI同级并随代码共同拉取；仓外手动部署以用户本地`config.env`的`project_root`解析代码相对引用。项目manifest视图由各项目自行适配，具体方案留待手工补充，见[部署与视图配置说明](docs-llm-wiki/知识库详细设计.md#7-部署方式与manifest视图配置)。本次仅更新文档，不增加WiFi Demo开发范围。

| 目录 | 存放内容 |
|---|---|
| `docs-raw/` | 五类已落地原件；`sources/` 仅后续来源登记占位 |
| `governance/` | Schema、受控枚举、模板、规范及来源锁 |
| `knowledge/` | 七类正式知识卡及导航，当前无业务卡 |
| `.build/` | 本地候选与转换暂存，生成内容不上库 |
| `logs/` | 已发生操作的持久记录，当前为空 |
| `docs-llm-wiki/` | 平铺设计、模块任务与入口文件及 SDD 工件 |
| `evals/` | 当前契约、Workflow、跨节点与进程恢复验收及分包运行入口 |
| `artifacts/` | 本地派生索引与报告，生成内容不上库 |

FactumCore 承载业务、知识与能力源码，`main/` 目前仍为空。18个节点Skill（详设v4列明）在根`skills/common/knowledge/`，两个Workflow在根`workflows/common/knowledge/`，与main同级，统一使用当前远端，不放嵌套`.git`。实际运行、安装和发行版本以knowledge-v2验收记录为准。

本轮按knowledge-v2进入开发；knowledge-v1原字节保留，新节点交付以当前记录为准。旧实现、测试和根开发工具的归档与历史成绩只属于当时版本，详见[历史布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)。领域内的`check.py/check.sh`按当前票据提供薄入口，不以空壳或旧报告宣称通过。

T201–T210已完成开发及隔离机制验收，实际结果见[开发验收](docs-llm-wiki/sdd/knowledge-v2/records/development-acceptance-20261021.json)。200个唯一用例中199通过、1跳过；真实人动作、实际宿主隐式触发、业务六Target/三pair、业务CI与权限仍由T211独立验收。

第一次使用先看[初始化与使用教程](docs-llm-wiki/使用说明.md)。其他入口：[AGENTS.md](AGENTS.md)、[设计入口](docs-llm-wiki/README.md)、[当前SDD](docs-llm-wiki/sdd/knowledge-v2/README.md)与[贡献约定](CONTRIBUTING.md)。六 Target/三 pair 是逻辑登记；业务源码、宏、构建与实际版本在外层 `config.yml` 未提供时保持 unknown。
