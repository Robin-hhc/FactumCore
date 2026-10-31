# 安装依赖、Skill、Workflow 与项目入口

部署入口、源模板及能力源码均位于知识根，默认目录为 `repo/himate/himate-knowledge-wifi-mp/`。`repo/` 表示 manifest 工作区根，不要求自身是 Git 仓。进入知识根后运行部署入口。

Linux：

```sh
sh ./deploy.sh
```

Linux 入口默认使用 `python3`；可用 `--python` 或 `HIMATE_KNOWLEDGE_PYTHON` 选择解释器。示例：

```sh
sh ./deploy.sh --python 'PATH_TO_PYTHON' --skills-root 'OPENFLOW_SKILLS_ROOT' --cac-skills-root 'CAC_SKILLS_ROOT' --workflows-root 'WORKFLOWS_ROOT'
```

Windows PowerShell：

```powershell
.\deploy.ps1
```

Windows 入口默认使用 `python`，通过 `-Python` 选择解释器。两个平台都展示未指定安装目录的默认值，回车采用，也可输入自定义路径。`~` 表示当前执行用户的主目录。

| 内容 | 默认目录 | Linux 参数 / PowerShell 参数 |
|---|---|---|
| OpenFlow Skill | `~/.openflow/config/skills` | `--skills-root` / `-SkillsRoot` |
| CAC Skill | `~/.cac/skills` | `--cac-skills-root` / `-CacSkillsRoot` |
| OpenFlow Workflow | `~/.openflow/config/workflow-templates` | `--workflows-root` / `-WorkflowsRoot` |

脚本收集知识根 `skills/` 中含 `SKILL.md` 的能力包，以及 `workflows/` 中含 `workflow.yaml` 的模板包。两个 Skill 目标安装同一组包，Workflow 只安装到 OpenFlow 模板目录。先收集目录与项目入口覆盖选择、校验路径，再依次执行：

1. 向选定的 Python 执行一次锁定运行依赖的 pip 安装。
2. 删除三个目标内本次全部同名包的完整目录及旧内容。
3. 将新包复制到各自目标目录。

第一步使用的命令为：

```text
python -m pip install -r runtime/requirements.lock.txt
```

使用执行端已有的 Python 3.10–3.12；Linux 的 `--python`、Windows 的 `-Python` 指定运行部署后端和安装依赖的同一解释器。脚本不下载 Python、不创建虚拟环境。pip 失败时停止，保留全部旧包。

```powershell
.\deploy.ps1 -SkillsRoot 'OPENFLOW_SKILLS_ROOT' -CacSkillsRoot 'CAC_SKILLS_ROOT' -WorkflowsRoot 'WORKFLOWS_ROOT' -Python 'PATH_TO_PYTHON'
```

Linux 的 `--source-root`、Windows 的 `-SourceRoot` 指定另一份知识包根，默认是部署入口所在的知识根，不是 manifest 根。`sh ./deploy.sh --help` 查看共享后端参数。两种入口都调用同一 Python 后端，也可从知识根直接使用；不传 `--python` 时安装到当前解释器：

```text
python tools/deploy/deploy.py --skills-root SKILLS_ROOT --workflows-root WORKFLOWS_ROOT --python PATH_TO_PYTHON
```

目标直接按包名展开，例如 `<WorkflowsRoot>/hs-knowledge-ingest/workflow.yaml`；模板的 `layouts.yaml`、`README.md` 一同复制。同名包完整替换，包内旧文件全部清除；源码和目标根中的其他包保留。未列入本次部署的旧能力包由维护者按需处理。

## 复制项目入口

脚本以源知识根的 `../..` 定位 manifest 根，不再询问地址，也不通过 Git 查找：

| 知识根内源文件 | manifest 根目标 |
|---|---|
| `config.yml` | `config.yml` |
| `AGENTS-code-root.md` | `AGENTS.md` |

执行前对已有文件逐个询问是否覆盖，默认 `y`：回车覆盖，输入 `n` 保留对应文件；目标不存在时无需覆盖确认。包安装后按选择写入入口。源模板不会被移动或删除，实际配置与项目约定由维护者按业务项目维护。

自动化执行可加 `--non-interactive` 或 `-NonInteractive`，未指定目录采用默认值，已有项目入口按默认 `y` 覆盖。安装器不搬运知识根、不配置远端 SSH、不下载 Python、不创建虚拟环境、不注册宿主，也不追加部署后验证。宿主从实际安装目录加载能力；远端数据执行端仍需具备代码、配置、解释器与依赖。

开发测试统一位于 [evals/deploy/](../../evals/deploy/)，从 manifest 根通过 [evals 运行器](../../evals/README.md#执行) 的 `--groups deploy` 执行。测试使用临时目录、模拟 pip 和解释器记录器，验证包安装顺序、三路包替换、入口覆盖选择及跨平台参数传递；不会向用户安装目录实际部署。日常操作见[使用说明](../../docs-llm-wiki/使用说明.md)。
