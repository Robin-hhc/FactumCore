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

1. 向选定的 Python 安装 `runtime/requirements.lock.txt` 的完整 Docling 多格式解析与 OCR 依赖。
2. 优先复用源知识根 `artifacts/models/docling-cpu/` 中的完整模型；否则验证 `tools/deploy/models/manifest.json` 和内附 `docling-cpu/` 的文件及分片大小、SHA-256 和路径，自动合并分片并离线安装到运行目录。内附集合损坏则失败；未携带集合时才按显式下载选项获取模型。
3. 依赖和模型准备均成功后，删除三个目标内本次全部同名包的完整目录及旧内容，再将新包复制到各自目标目录。

第一步使用的命令为：

```text
python -m pip install -r runtime/requirements.lock.txt
```

唯一运行锁面向 Python 3.10–3.12，使用普通 `torch==2.14.1`、`torchvision==0.29.2` 发行包；解析器使用 CPU 推理。Linux 的 `--python`、Windows 的 `-Python` 指定运行部署后端、安装依赖和准备模型的同一解释器。包安装沿用已有 pip 配置，不指定或追加外网索引；内部镜像须提供锁定版本及其平台依赖，缺包时明确失败，不自动切换源。Linux 普通 PyTorch 会引入 CUDA 运行库等 Python 依赖，安装体积通常更大，OCR 仍按 CPU 运行。本地模型完整时复用；否则优先校验内附集合并离线安装，损坏集合明确失败。未携带模型且本地也缺失时，只有显式 `--download-models` / `-DownloadModels` 才访问模型来源。脚本不下载 Python、不创建虚拟环境。依赖安装或模型准备失败时停止，保留全部旧包和项目入口。

内附模型位于 `models/docling-cpu/`，由同级 `models/manifest.json` 固定大小与摘要，安装后为 8 个必需文件、416,177,665 字节，约 416.18 MB（396.90 MiB）。模型通过普通 Git 提交，不依赖 Git LFS；两个超过 100 MiB 的权重拆为不超过 48 MiB 的 `.part001` 等分片，部署自动校验并合并，无需手工处理。克隆或同步完整仓库即可取得权重；离线拷贝时保留这整个目录及匹配清单。

`--download-models` / `-DownloadModels` 显式允许未携带模型且本地缺失时下载。默认不访问模型站点，存在但损坏的内附集合不会触发下载回退。


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

开发测试统一位于 [evals/deploy/](../../evals/deploy/)，从 manifest 根通过 [evals 运行器](../../evals/README.md#执行) 的 `--groups deploy` 执行。测试使用临时目录、模拟依赖安装、模型准备和解释器记录器，验证准备顺序、内附清单与小型合成模型的完整性和离线复制、损坏集合不联网、失败保留旧包、三路包替换、入口覆盖选择及平台入口参数传递；不会向用户安装目录实际部署。模拟测试不代替执行端真实安装和 OCR 验证。日常操作见[使用说明](../../docs-llm-wiki/使用说明.md)。
