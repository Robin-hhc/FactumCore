# 部署与执行

## Windows 部署入口

首次安装或本机依赖缺项时，在包含分发源码和 `deploy.ps1` 的 Windows 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

脚本询问 Skill、Workflow 和知识项目根三条路径。第三条是项目根，不是知识根：已有 `config.yml` 时沿用其中 `knowledge_roots.wifi`，允许安全嵌套；没有配置时使用项目根下的 `himate-knowledge-wifi-mp/`。完整默认值、参数和保留策略见实际知识根 `docs-llm-wiki/使用说明.md` 的“首次环境安装”。

脚本选择本机已有 Python 3.10–3.12；找不到时由用户先安装，或用 `-Python` 指定实际解释器，不自动下载 Python。默认核对该解释器的配套运行锁，交互模式发现缺包时询问是否修复；非交互修复须显式提供 `-InstallDependencies`。安装和后续部署使用同一个解释器。只看计划使用 `-Plan`，自动化可显式指定 `-SkillsRoot`、`-WorkflowsRoot`、`-ProjectRoot` 和 `-NonInteractive`。

三份 ZIP 在本机临时生成；知识 ZIP 整体复制到项目根内本批暂存位置，再由 Windows 直接在目标路径解压并逐文件回读核对 SHA-256。映射共享盘仍有小文件写入开销，这不代表服务器本地解压，也不证明服务器 Python 或依赖可用。

已有项目的配置、根 `AGENTS.md`、原件、卡及导航、来源锁和正式记录保留；治理规则和 `framework.lock.yaml` 成套更新。脚本不改宿主 SSH／MCP／权限开关，不安装或初始化 CodeGraph。完成后重启 OpenFlow、核对能力列表，并用新任务验证；已有 Workflow 副本不自动升级。

## 日常项目发现

已有部署和有效项目上下文时，直接按 [任务入口](../SKILL.md) 使用业务能力。缺少上下文才调用 [只读发现 CLI](public-api.md)，读取真实 `AGENTS.md`、`config.yml`、K 入口及所需规则；发现过程不安装包、不登记能力，也不生成业务处理义务。

`repo/` 表示实际业务工作区，`K` 是其 `config.yml` 解析出的知识根，`S`、`F` 是实际已安装能力目录。原件、卡、治理及运行产物沿用 K 的现有布局；请求和稿件在 `.build/`，正式记录在 `logs/`，索引和报告在 `artifacts/`。

## 远端任务与代码图谱

目标代码仓在远端时，先由用户或部署维护者在 OpenFlow 配置、启用并验证 SSH MCP，让需要远端执行的角色可调用它。Agent 通过该 MCP 在实际远端项目根执行业务脚本和仓库操作，另核对该端 Python、配套依赖和已安装 Skill 路径。Windows 部署脚本不建立 SSH 连接，本机检查结果不能代替执行端检查。

SSH 结果不明或连接中断时，先核对原执行端进程、操作记录、journal 和活动代，再决定续办；不推断远端未执行，也不重复已提交写入。

CodeGraph 仍按 [首次初始化 CodeGraph](../SKILL.md#首次初始化-codegraph) 由 Agent 使用源码所在端已有 CLI 逐仓处理；已有索引复用，空模块列表不建图。MCP 由宿主提供，缺项如实报告。部署完成不代表 CodeGraph、Workflow 调度或知识业务验收通过。

## 旧 setup 的显式诊断

`scripts/setup.py` 保留诊断与兼容用途，常规安装统一使用上面的部署入口。仅明确要求诊断时，使用实际执行端的解释器和已安装路径，例如只检查依赖：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml --check-only
```

`ready` 只说明该解释器依赖匹配且项目配置已读取；`missing_dependencies` 和 `failed` 保留实际缺项。它不部署能力、不配置 MCP，也不代替项目或 Workflow 验证；不要为每次 ingest、query、lint 或 status 自动调用。
