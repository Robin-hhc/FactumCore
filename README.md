# FactumCore

AIoTBot WiFi 知识系统的设计、共享实现与领域资产统一在本仓维护。用户于 2026-10-19 指定当前采用单仓：原 `docs/` 已迁移为 `docs-llm-wiki/`，`aiot-wifi-knowledge/` 直接位于仓根。

| 路径 | 职责 |
|---|---|
| [总体设计入口](docs-llm-wiki/设计文档/README.md) | 当前主设计、详细设计和历史稿状态 |
| [SDD 总入口](docs-llm-wiki/sdd/knowledge-v1/README.md) | 18 需求、9 模块、28 任务、149 路径与 34 验收 |
| `skills/common/knowledge/_shared/` | 公共 CLI、契约与执行程序；当前完成状态以 SDD 记录为准 |
| `workflows/` | 生产与治理编排的实施落点 |
| [WiFi 领域入口](aiot-wifi-knowledge/AGENTS.md) | raw 原件、治理契约、正式卡及域内记录 |
| `config.yml` | 六逻辑 Target、三候选 pair 与实际项目映射；未知配置保持 unknown |
| `docs-llm-wiki/research/`、`experiments/` | 调研证据、协议与实际运行；不自动成为正式知识卡 |

T01/T02 已有契约与项目发现的验证记录。下一批按 T03 → T05 → T06 → T07 打通 raw 捕获、候选、人工确认与 stable 事务；真实业务原件和技术卡当前为空。宿主隐式 Skill 触发、真实 WiFi 源码/构建、六 Target/三 pair 和外部 ACL 分别验收。

创建 Python ≥3.12 虚拟环境并按锁安装依赖后，在本仓根运行：

```powershell
.\.venv\Scripts\python.exe skills/common/knowledge/_shared/cli.py contract validate --knowledge-root aiot-wifi-knowledge --kind workspace --input config.yml
.\.venv\Scripts\python.exe tools/validate_sdd.py
New-Item -ItemType Directory -Force artifacts/test-tmp | Out-Null
.\.venv\Scripts\python.exe -m pytest -q --basetemp=artifacts/test-tmp/local-check
.\.venv\Scripts\ruff.exe check skills/common/knowledge/_shared tools
```

并发测试分别指定末级 basetemp，不使用现有业务目录。单仓只改变当前开发与发布布局；框架分发仍须排除组内事实，目录和 Git ignore 不提供访问控制。旧 `aiot-knowledge/` 和 `.worktrees/` 不参与本轮交付。

[迁移与字节核验记录](docs-llm-wiki/sdd/knowledge-v1/records/single-repo-migration.md) 保留本轮路径决议、迁移摘要和历史验证边界。
