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

部署会向该 Python 安装工具包 `runtime/requirements.lock.txt` 中锁定的依赖，然后替换三个安装目录内本次发行的同名能力包。Linux 默认解释器为 `python3`，可通过 `--python` 或 `HIMATE_KNOWLEDGE_PYTHON` 指定。Windows 默认使用 `python`，可通过 `-Python` 指定。脚本沿用执行端的 pip 配置，不下载 Python，也不创建虚拟环境。安装过程中会输出实际的 CLI 路径。

| 内容 | 默认目录 | Linux / PowerShell 参数 |
|---|---|---|
| OpenFlow Skill | `~/.openflow/config/skills` | `--skills-root` / `-SkillsRoot` |
| CAC Skill | `~/.cac/skills` | `--cac-skills-root` / `-CacSkillsRoot` |
| OpenFlow Workflow | `~/.openflow/config/workflow-templates` | `--workflows-root` / `-WorkflowsRoot` |

交互安装会询问未指定的目录，回车采用默认值。自动化使用 `--non-interactive` / `-NonInteractive`。`--source-root` / `-SourceRoot` 指定工具包，默认使用部署入口所在目录。能力包单独存放时用 `--capabilities-root` / `-CapabilitiesRoot` 指向同时包含 `skills/` 和 `workflows/` 的目录。未设置时优先使用相邻的 `himate-skills`，其次兼容旧工具包根下的 `skills/` 和 `workflows/`。部署按 `SKILL.md` 和 `workflow.yaml` 识别待安装的包，按包名替换并保留目标目录的其他包。

安装后用同一解释器运行共享 CLI，命令显式绑定实际知识库：

```text
<已准备的 Python> -B <工具包>/knowledge.py doctor --knowledge-root <知识库> --json
```

OpenFlow 宿主通过绝对路径 `OPENFLOW_KNOWLEDGE_TOOLKIT_ROOT` 指定工具包目录，可用 `OPENFLOW_KNOWLEDGE_PYTHON` 指定 Python 绝对路径。面板中另选需要操作的知识库。SSH 执行使用远端的工具包、解释器和知识库原生路径。OpenFlow 的面板命令以宿主配置为准。终端可以通过环境安装注册 `knowledge`，或单独运行 `<Python> -B <工具包>/knowledge.py install-command`。

日常升级时，将新版工具包放在约定的工具目录，使用同一解释器重新安装。若工具包或解释器迁移，更新宿主配置并重跑环境安装，以更新工具包管理的 `knowledge` 命令。知识库维护者继续在自己的库中维护 `config.yml` 和 `AGENTS.md`。

## 检查或安装宿主运行环境

`knowledge doctor --environment-only --json` 只读检查锁定的 Python 依赖和命令入口。`needs_install` 表示需要补齐依赖，`needs_cli` 表示命令待注册或待修复，`ready` 表示环境就绪。终端和 OpenFlow 都能在绑定前调用这项检查。

`knowledge setup` 用同一个 Python 按需补齐依赖，再确认 npm 或手动部署的命令入口。OpenFlow 在宿主执行 `setup --jsonl`，展示阶段进度并在结束后复查。首次手动注册前，用 `<Python> -B <工具包>/knowledge.py` 加上同样的子命令。环境操作无需传知识根。`tools/deploy/environment.py check|install` 保留原有自动化接口。

通过 npm 部署时，`setup` 复用 npm 注册的入口。手动部署时，Windows 默认把命令放到 `%LOCALAPPDATA%\HiMate\bin` 并加入执行账户的用户 `PATH`。Linux 默认命令目录为 `~/.local/bin`，由终端或服务配置 `PATH`。手动部署可以用 `--bin-dir` 选择命令目录。在 Windows 单独注册时可运行 `install-command --add-path`。打开新终端后可运行 `knowledge --version` 确认入口。

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

优先复用知识库已有完整模型，否则按工具包 `tools/deploy/models/manifest.json` 校验随包模型及分片的大小、SHA-256 和路径，再离线安装。离线模型安装后有 8 个文件，共 416,177,665 字节。保留工具包中的完整 `models/docling-cpu/` 和匹配清单即可分发这一套模型。模型准备或依赖安装失败会保留已经安装的 Skills 和 Workflows。

若工具包未携带模型、知识库本地也缺少模型，可以显式加 `--download-models` / `-DownloadModels` 并指定知识库。携带但损坏的模型会直接报错。OCR 推理使用 CPU。普通 PyTorch 安装可能同时下载发行包要求的其他运行库，需由执行端现有 pip 镜像提供锁定依赖。

日常使用说明随领域知识库提供，见该库的 `docs-llm-wiki/使用说明.md`。工具包内的[面板 CLI 契约](../../docs-llm-wiki/面板CLI契约.md)说明宿主调用方式，[模型来源](models/README.md)记录离线模型的来源和校验信息。部署测试使用隔离目录、模拟依赖安装和解释器记录器，覆盖工具与数据目录分离、各安装目标、模型校验、失败保护和入口参数传递。通过 [evals 运行器](../../evals/README.md) 的 `--groups deploy` 执行。
