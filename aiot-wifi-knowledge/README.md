# WiFi 知识库

这是 FactumCore 单仓内唯一的领域目录，Git 操作统一在 FactumCore 根执行。整体布局遵循[总体设计 §5.3](docs-llm-wiki/AIoTBot知识库架构设计.md#53-aiotbot-knowledge目录架构)。

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

当前只保留目录骨架及已有治理资产，外层 `main/`、四个 Skill、两个 Workflow 均为空占位。旧执行实现、测试及根开发工具已归档仓外；历史测试通过不代表当前仓可调用相应能力，详见[布局记录](docs-llm-wiki/sdd/knowledge-v1/records/workspace-layout-20261020.md)。`check.py/check.sh` 等程序仍须按 SDD 开发，不生成空壳通过检查。

先读 [AGENTS.md](AGENTS.md)、[设计入口](docs-llm-wiki/README.md)与[贡献约定](CONTRIBUTING.md)。六 Target/三 pair 是逻辑登记；业务源码、宏、构建与实际版本在外层 `config.yml` 未提供时保持 unknown。
