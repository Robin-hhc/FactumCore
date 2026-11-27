# HiMate Skills 和 Workflows

本仓维护 Agent 的步骤指引、参考资料、写作模板和工作流编排。`skills/` 提供各 Skill，`workflows/` 提供 OpenFlow 工作流，根目录的 deploy 脚本负责把这些能力包安装到宿主。

各 Skill 提供完整的任务方法、判断标准和所需 CLI 指引，可在不同 harness 中独立使用。CLI 执行确定性的业务操作和校验，MCP 将这些能力适配为宿主工具，Workflow 维护节点顺序、角色和交接。模板、检索策略和内容判断仍由相应 Skill 维护。

已有 Knowledge MCP 工具时，Agent 沿用工具绑定的知识根。没有 Knowledge MCP 时，沿已确认的知识根、账户和执行端，通过本机终端或已授权的 SSH 工具、`ssh` 命令调用 CLI；远端命令和路径均在同一执行端核对。只在明确缺少 CLI、启动入口或运行依赖时加载 [`hs-knowledge-setup`](skills/hs-knowledge-setup/README.md)，就绪后继续原任务。Setup 准备该执行端的 CLI 和依赖，不以配置 MCP 为前提，也不自动修改各 harness 的 MCP 配置。

已采用 Knowledge MCP 的任务遇到工具缺失、权限拒绝、连接失败或 `blocked` 时，按该诊断处理，不自动改走终端或另一执行端绕过限制。独立使用 Skill 与宿主内受控 Workflow 的工具授权范围分别沿用所在环境的约束。

## 安装能力包

进入本仓目录，按系统执行对应入口。脚本通过 Python 标准库读取本仓的 `skills/` 和 `workflows/`，逐项询问安装目录，回车使用默认值。

### Windows PowerShell

```powershell
.\deploy.ps1
```

### Linux

```sh
sh ./deploy.sh
```

| 安装内容 | 默认目录 | PowerShell 参数 | Linux 参数 |
|---|---|---|---|
| OpenFlow Skills | `~/.openflow/config/skills` | `-SkillsRoot` | `--skills-root` |
| CAC Skills | `~/.cac/skills` | `-CacSkillsRoot` | `--cac-skills-root` |
| OpenFlow Workflows | `~/.openflow/config/workflow-templates` | `-WorkflowsRoot` | `--workflows-root` |

自动化使用 `-NonInteractive` 或 `--non-interactive`，采用默认目标目录并跳过询问。

```powershell
.\deploy.ps1 -NonInteractive
```

```sh
sh ./deploy.sh --non-interactive
```

默认安装脚本所在仓的能力。需要安装另一份能力包时，用 `-CapabilitiesRoot` 或 `--capabilities-root` 指定包含 `skills/` 和 `workflows/` 的目录。PowerShell 可用 `-Python` 指定运行脚本的解释器，Linux 可用 `--python` 或 `HIMATE_KNOWLEDGE_PYTHON` 指定。

安装时按 `SKILL.md` 和 `workflow.yaml` 识别包，更新时完整替换同名包并保留其他包。完成后启动或重启 OpenFlow，让宿主加载已安装的能力。

## 目录

```text
himate-skills/
├── README.md
├── deploy.ps1
├── deploy.sh
├── scripts/deploy.py
├── evals/deploy/
├── skills/
└── workflows/
```

Agent 在相应节点加载 Skill 后，使用该节点提供的 Knowledge MCP 工具。采用 CLI 的节点按随包指引调用该执行端已安装的 CLI。安装器和安装测试随本仓维护。

## 验证安装器

使用具备 pytest 的开发环境，从本仓根执行以下命令。测试在临时目录验证复制、更新、路径保护及 Windows、Linux 入口，运行报告按实际平台记录。

```sh
python -m pytest evals/deploy -q
```
