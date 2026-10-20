# WiFi 知识库

这是 FactumCore 根下的 `aiotbot-knowledge-wifi/`，本次唯一领域目录，无中间目录，不创建其他领域占位。Git 操作统一在 FactumCore 根执行，整体布局遵循[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)目录树。

| 目录 | 存放内容 |
|---|---|
| `docs-raw/` | 五类已落地原件；`sources/` 仅后续来源登记占位 |
| `governance/` | Schema、受控枚举、模板、规范及来源锁 |
| `knowledge/` | 七类正式知识卡及导航，当前无业务卡 |
| `.build/` | 本地候选与转换暂存，生成内容不上库 |
| `logs/` | 已发生操作的持久记录，当前为空 |
| `docs-llm-wiki/` | 四个平铺设计/入口文件及 SDD 工件 |
| `evals/` | 后续验收案例与运行入口，当前为空 |
| `artifacts/` | 本地派生索引与报告，生成内容不上库 |

FactumCore 承载业务与知识，`main/` 目前仍为空。四个共享 Skill（`hs-workspace-explore`、`hs-knowledge-ingest`、`hs-knowledge-lint`、`hs-knowledge-query`）以及生产、治理 Workflow 归独立能力仓，本仓已移除旧占位。能力仓根、URL、版本和安装状态尚未提供，不能据此运行生产、治理或查询。

本轮只完善目录和设计，保留既有 SDD 原字节，后续再重新基线并按任务开发。旧实现、测试和根开发工具已归档，历史成绩只属于当时版本，详见[历史布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)。领域内的 `check.py/check.sh` 仍为待实现检查入口，不生成空壳通过检查。

先读 [AGENTS.md](AGENTS.md)、[设计入口](docs-llm-wiki/README.md)与[贡献约定](CONTRIBUTING.md)。六 Target/三 pair 是逻辑登记；业务源码、宏、构建与实际版本在外层 `config.yml` 未提供时保持 unknown。
