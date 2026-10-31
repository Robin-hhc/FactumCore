# 安装 Skill、Workflow 与运行依赖

从包含部署入口、`tools/`、`skills/` 和 `workflows/` 的完整源码仓根执行。

Linux：

```sh
sh ./deploy.sh
```

Linux 入口默认使用 `python3`，非交互；可用 `--python` 或 `HIMATE_KNOWLEDGE_PYTHON` 选择解释器。示例：

```sh
sh ./deploy.sh --python 'PATH_TO_PYTHON' --skills-root 'SKILLS_ROOT' --workflows-root 'WORKFLOWS_ROOT'
```

Windows PowerShell：

```powershell
.\deploy.ps1
```

Windows 入口默认使用 `python`，未指定安装目录时交互询问。两种入口的默认目标均为：Skill 位于 `~/.openflow/config/skills`，Workflow 模板位于 `~/.openflow/config/workflow-templates`。

脚本先收集 `repo/skills/common/knowledge/` 中含 `SKILL.md` 的能力包，以及 `repo/workflows/common/knowledge/` 中含 `workflow.yaml` 的模板包，并校验源码和目标路径。随后严格执行三步：

1. 向选定的 Python 执行一次锁定运行依赖的 pip 安装。
2. 删除本次将部署的全部同名 Skill、Workflow 包目录及其旧内容。
3. 将新包复制到各自目标目录。

第一步使用的命令为：

```text
python -m pip install -r repo/himate/himate-knowledge-wifi-mp/runtime/requirements.lock.txt
```

使用执行端已有的 Python 3.10–3.12；Linux 的 `--python`、Windows 的 `-Python` 指定运行部署后端和安装依赖的同一解释器。脚本不下载 Python、不创建虚拟环境。pip 失败时停止，保留全部旧包。

```powershell
.\deploy.ps1 -NonInteractive -SkillsRoot 'SKILLS_ROOT' -WorkflowsRoot 'WORKFLOWS_ROOT' -Python 'PATH_TO_PYTHON'
```

Linux 的 `--source-root`、Windows 的 `-SourceRoot` 可指定另一份完整源码仓。`sh ./deploy.sh --help` 查看共享后端参数。两种入口都调用同一 Python 后端，也可直接使用；不传 `--python` 时安装到当前解释器：

```text
python tools/deploy/deploy.py --skills-root SKILLS_ROOT --workflows-root WORKFLOWS_ROOT --python PATH_TO_PYTHON
```

目标直接按包名展开，例如 `<WorkflowsRoot>/hs-knowledge-ingest/workflow.yaml`；模板的 `layouts.yaml`、`README.md` 一同复制。同名包完整替换，包内旧文件全部清除；源码和目标根中的其他包保留。宿主从目标目录加载能力和模板。知识仓、项目入口及配置由项目自身管理；安装器不创建业务配置或知识根、不配置远端 SSH、不制作压缩包、不注册宿主，也不追加部署后验证。未列入本次部署的旧能力包由维护者按需处理。

开发测试统一位于 [evals/deploy/](../../himate/himate-knowledge-wifi-mp/evals/deploy/)，从项目根通过 [evals 运行器](../../himate/himate-knowledge-wifi-mp/evals/README.md#执行) 的 `--groups deploy` 执行。测试使用临时目录、模拟 pip 和解释器记录器，验证三步顺序、pip 失败时旧包保留、同名包完整替换、其他包与源码保留，以及 Linux/PowerShell 入口的参数和退出码传递；不会向本机环境实际安装依赖。部署后的日常操作见[使用说明](../../himate/himate-knowledge-wifi-mp/docs-llm-wiki/使用说明.md)。
