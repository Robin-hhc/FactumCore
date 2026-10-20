# FactumCore

AIoTBot WiFi 知识系统的设计、共享实现与领域资产统一在本仓维护。用户于 2026-10-19 指定当前采用单仓：原 `docs/` 已迁移为 `docs-llm-wiki/`，`aiot-wifi-knowledge/` 直接位于仓根。

| 路径 | 职责 |
|---|---|
| [总体设计入口](docs-llm-wiki/设计文档/README.md) | 当前主设计、详细设计和历史稿状态 |
| [SDD 总入口](docs-llm-wiki/sdd/knowledge-v1/README.md) | 18 需求、9 模块、28 任务、148 路径与 34 验收 |
| `skills/common/knowledge/_shared/` | 公共 CLI、契约与执行程序；当前完成状态以 SDD 记录为准 |
| `workflows/` | 生产与治理编排的实施落点 |
| [WiFi 领域入口](aiot-wifi-knowledge/AGENTS.md) | raw 原件、治理契约、正式卡及域内记录 |
| `config.yml` | 六逻辑 Target、三候选 pair 与实际项目映射；未知配置保持 unknown |
| `docs-llm-wiki/research/`、`experiments/` | 调研证据、协议与实际运行；不自动成为正式知识卡 |

已有模块包括契约、项目发现，以及 raw 捕获 → 显式候选/final-view → 人工确认 → stable 事务的本地链。[raw 手工操作链](docs-llm-wiki/sdd/knowledge-v1/document-chain-usage.md) 说明实际命令、真人确认、部分接受与错误处理；[验收记录入口](docs-llm-wiki/sdd/knowledge-v1/records/README.md)和[本批最终验收](docs-llm-wiki/sdd/knowledge-v1/records/T07-verification.md)保存实际结果，状态以[任务入口](docs-llm-wiki/sdd/knowledge-v1/tasks.md)为准。真实业务原件和技术卡当前为空；宿主隐式 Skill 触发、真实 WiFi 源码/构建、六 Target/三 pair 和外部 ACL 分别验收。

使用 Python 3.12 创建虚拟环境，按固定依赖安装后，在本仓根运行；以下安装命令由操作者按环境执行，工具运行不自动下载依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
.\.venv\Scripts\python.exe skills/common/knowledge/_shared/cli.py contract validate --knowledge-root aiot-wifi-knowledge --kind workspace --input config.yml
.\.venv\Scripts\python.exe tools/validate_sdd.py
New-Item -ItemType Directory -Force artifacts/test-tmp | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp=artifacts/test-tmp/local-check
.\.venv\Scripts\ruff.exe check skills/common/knowledge/_shared tools
```

并发测试分别指定末级 basetemp，不使用现有业务目录。单仓只改变当前开发与发布布局；框架分发仍须排除组内事实，目录和 Git ignore 不提供访问控制。旧 `aiot-knowledge/` 和 `.worktrees/` 不参与本轮交付。

本批 raw 链由操作者显式调用 CLI；完整 Skill/Workflow 自动编排仍属于 T20/T21。文档人工确认要求真实人控制的交互终端并输入当前最终视图挑战，不能由 Agent 代填；聊天确认的可信适配器尚未接入。`ingest apply` 只负责本地 stable 落位，不执行 Git 或建立索引。

[迁移与字节核验记录](docs-llm-wiki/sdd/knowledge-v1/records/single-repo-migration.md) 保留本轮路径决议、迁移摘要和历史验证边界。
