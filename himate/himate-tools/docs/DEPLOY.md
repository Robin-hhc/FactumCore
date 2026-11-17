# 安装知识库工具包

将部门发布的 `himate-tools` 和 `himate-skills` 放在执行机器的同一级目录，从工具包运行安装入口。工具包可以和知识库放在不同磁盘，也可以放在同一工作区的并列目录。每台执行机器需要一个 Python 3.10–3.12 环境。

Linux：

```sh
sh '/opt/himate/himate-tools/deploy.sh' --python '/opt/himate-venv/bin/python' --non-interactive
```

Windows PowerShell：

```powershell
& 'D:\HiMate\himate-tools\deploy.ps1' -Python 'D:\HiMate Python\Scripts\python.exe' -NonInteractive
```

部署使用选定的 Python 调用 `knowledge setup --dependencies-only`，检查锁定的依赖，有缺失时安装。依赖和所需 OCR 模型就绪后，替换三个安装目录内本次发行的同名能力包。Linux 默认解释器为 `python3`，可通过 `--python` 或 `HIMATE_KNOWLEDGE_PYTHON` 指定。Windows 默认使用 `python`，可通过 `-Python` 指定。安装过程中会输出实际的 CLI 路径。

| 内容 | 默认目录 | Linux / PowerShell 参数 |
|---|---|---|
| OpenFlow Skill | `~/.openflow/config/skills` | `--skills-root` / `-SkillsRoot` |
| CAC Skill | `~/.cac/skills` | `--cac-skills-root` / `-CacSkillsRoot` |
| OpenFlow Workflow | `~/.openflow/config/workflow-templates` | `--workflows-root` / `-WorkflowsRoot` |

交互安装会询问未指定的目录，回车采用默认值。自动化使用 `--non-interactive` / `-NonInteractive`。`--source-root` / `-SourceRoot` 指定工具包，默认使用部署入口所在目录。能力包单独存放时用 `--capabilities-root` / `-CapabilitiesRoot` 指向同时包含 `skills/` 和 `workflows/` 的目录。未设置时优先使用相邻的 `himate-skills`，其次兼容旧工具包根下的 `skills/` 和 `workflows/`。部署按 `SKILL.md` 和 `workflow.yaml` 识别待安装的包，按包名替换并保留目标目录的其他包。

如果通过 npm 安装 CLI，npm 会在全局命令目录注册 `knowledge`。源码部署保留现有的命令注册和 PATH 配置。需要注册 `knowledge` 时，从工具包内部入口运行完整的 `setup`，它会复用已就绪的依赖。

```text
<已准备的 Python> -B <工具包>/knowledge.py setup --json
```

注册后，运行 `knowledge doctor --knowledge-root "<知识根绝对路径>" --json` 核对库配置和工具版本。OpenFlow 默认从宿主账户的 PATH 查找 `knowledge`。从 npm 安装后，确保 npm 全局命令目录已经进入启动 OpenFlow 的环境，再启动或重启宿主。面板中另选需要操作的知识库。通过 SSH 执行时，在远端准备 `knowledge`，使用远端的知识根路径。

日常升级用 npm 安装新版，再检查环境。源码部署可继续用 `OPENFLOW_KNOWLEDGE_TOOLKIT_ROOT` 显式指向工具包的绝对目录。切换到 npm 时移除该项配置，并在宿主启动环境验证 `knowledge --version`。知识库维护者继续在自己的库中维护 `config.yml` 和 `AGENTS.md`。

## 检查或安装宿主运行环境

`knowledge doctor --environment-only --json` 只读检查选定的 Python、锁定依赖和命令入口。`needs_install` 表示依赖缺失或版本不匹配，`needs_cli` 表示命令待注册或待修复，`ready` 表示环境就绪。终端和 OpenFlow 都能在绑定前调用这项检查。

`knowledge setup` 通过选定的 Python 执行 `<Python> -m pip install -r <工具包>/runtime/requirements.lock.txt`，随后用同一解释器复查。安装沿用本机 pip 的软件源与代理设置，并遵守发行版策略。所选 Python 需要已有 pip 和可写的安装位置。报告中的 `python` 和 `python_version` 给出安装目标的解释器路径和版本。

终端与 OpenFlow 可以共用 `HIMATE_KNOWLEDGE_PYTHON`，指向解释器绝对路径。也可以用宿主的 `OPENFLOW_KNOWLEDGE_PYTHON` 单独指定 OpenFlow 使用的解释器。更改宿主启动环境后重启。需要使用已有虚拟环境时，指定该环境内的 Python。

检查显示 `DEPENDENCY_PIP_MISSING` 时，选择带 pip 的 Python。系统发行版限制安装或权限不足时，选择允许安装依赖的解释器，按需要更新相应配置，再运行 `knowledge setup`。

OpenFlow 的环境检查调用 `doctor --environment-only --json`。安装调用 `setup --jsonl`，用 CLI 输出的阶段事件显示进度，以同一命令返回的最终环境报告为准。环境操作无需传知识根。使用旧环境脚本的自动化可切换到这两个 CLI 命令。安装失败时按结果中的原因及本机日志定位问题。

通过 npm 部署时，`setup` 复用 npm 全局命令目录的启动器。手动部署时，Windows 默认生成 `%LOCALAPPDATA%\HiMate\bin\knowledge.cmd` 并将目录加入执行账户的用户 `PATH`。Linux 默认生成 `~/.local/bin/knowledge`，由终端或服务配置 `PATH`。手动部署可以用 `--bin-dir` 选择命令目录。Windows 已准备依赖时，管理员也可用首次注册示例中的内部入口执行 `install-command --add-path`。打开新终端后运行 `knowledge --version` 确认入口。

## 为现有知识库准备 OCR

只需查询、录入常规文档或安装能力时，安装无需指定知识库。需要 `standard` OCR 时，为对应知识库另加 `--knowledge-root` / `-KnowledgeRoot`。该目录必须已经存在并包含 `config.yml`，模型安装到该知识库的 `artifacts/models/docling-cpu/`。

```sh
sh '/opt/himate/himate-tools/deploy.sh' --python '/opt/himate-venv/bin/python' --non-interactive \
  --knowledge-root '/srv/knowledge/WiFi KB'
```

```powershell
& 'D:\HiMate\himate-tools\deploy.ps1' -Python 'D:\HiMate Python\Scripts\python.exe' -NonInteractive `
  -KnowledgeRoot 'E:\Knowledge\WiFi KB'
```

优先复用知识库已有完整模型。否则部署按 `distribution/models/manifest.json` 校验随源码分发的模型及分片，再离线安装。通过 npm 安装的模型包沿用工具安装目录的 `tools/deploy/models/`，部署也识别该位置。离线模型安装后有 8 个文件，共 416,177,665 字节。模型准备或依赖安装失败会保留已经安装的 Skills 和 Workflows。

若工具包未携带模型、知识库本地也缺少模型，可以显式加 `--download-models` / `-DownloadModels` 并指定知识库。携带但损坏的模型会直接报错。OCR 推理使用 CPU。普通 PyTorch 安装可能同时下载发行包要求的其他运行库，需由执行端现有 pip 镜像提供锁定依赖。

日常使用说明随领域知识库提供，见该库的 `docs-llm-wiki/README.md`。[面板 CLI 契约](面板CLI契约.md)说明宿主调用方式，[模型来源](../distribution/models/README.md)记录离线模型的来源和校验信息。部署测试使用隔离目录、模拟依赖安装和解释器记录器，覆盖工具与数据目录分离、各安装目标、模型校验、失败保护和入口参数传递。通过 [evals 运行器](../evals/README.md) 的 `--groups deploy` 执行。
