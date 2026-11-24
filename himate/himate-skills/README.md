# HiMate Skills 和 Workflows

本仓维护 Agent 的步骤指引、参考资料、写作模板和工作流编排。`skills/` 提供各 Skill，`workflows/` 提供 OpenFlow 工作流，根目录的 deploy 脚本负责把这些能力包安装到宿主。

使用前，在实际执行端通过 npm 安装 `@himate/knowledge-models` 和 `@himate/knowledge-cli`，运行 `knowledge --version` 和 `knowledge setup`。当前会话提供对应的 Knowledge MCP 工具时，Agent 沿用工具绑定的知识根。采用 CLI 方式时，从已确认的执行端运行 `knowledge`。

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
