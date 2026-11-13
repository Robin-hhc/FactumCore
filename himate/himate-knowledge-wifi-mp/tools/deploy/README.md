# 安装依赖、OCR 模型、Skill 和 Workflow

部署入口和能力源码位于知识根。默认布局为 `repo/himate/himate-knowledge-wifi-mp/`，`repo/` 表示 manifest 工作区根。进入知识根后运行部署入口。

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

脚本收集知识根 `skills/` 中含 `SKILL.md` 的能力包，以及 `workflows/` 中含 `workflow.yaml` 的模板包。两个 Skill 目标安装同一组包，Workflow 安装到 OpenFlow 模板目录。确认三个安装目录后依次执行：

1. 向选定的 Python 安装 `runtime/requirements.lock.txt` 的完整 Docling 多格式解析与 OCR 依赖。
2. 优先复用源知识根 `artifacts/models/docling-cpu/` 中的完整模型；否则验证 `tools/deploy/models/manifest.json` 和内附 `docling-cpu/` 的文件及分片大小、SHA-256 和路径，自动合并分片并离线安装到运行目录。内附集合损坏则失败；未携带集合时才按显式下载选项获取模型。
3. 依赖和模型准备均成功后，删除三个目标内本次全部同名包的完整目录及旧内容，再将新包复制到各自目标目录。

第一步使用的命令为：

```text
python -m pip install -r runtime/requirements.lock.txt
```

唯一运行锁面向 Python 3.10–3.12，使用普通 `torch==2.14.1`、`torchvision==0.29.2` 发行包；解析器使用 CPU 推理。Linux 的 `--python`、Windows 的 `-Python` 指定运行部署后端、安装依赖和准备模型的同一解释器。包安装沿用已有 pip 配置，不指定或追加外网索引；内部镜像须提供锁定版本及其平台依赖，缺包时明确失败，不自动切换源。Linux 普通 PyTorch 会引入 CUDA 运行库等 Python 依赖，安装体积通常更大，OCR 仍按 CPU 运行。本地模型完整时复用；否则优先校验内附集合并离线安装，损坏集合明确失败。未携带模型且本地也缺失时，只有显式 `--download-models` / `-DownloadModels` 才访问模型来源。脚本不下载 Python、不创建虚拟环境。依赖安装或模型准备失败时停止，保留已安装的能力包。

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

## 知识根配置

维护者在实际知识根直接维护 `config.yml` 和 `AGENTS.md`。升级时按[使用说明](../../docs-llm-wiki/使用说明.md#首次安装)迁入现有项目的实际配置及约定。宿主选定知识根后从该目录运行 CLI。

自动化执行可加 `--non-interactive` 或 `-NonInteractive`，未指定的安装目录采用默认值。宿主从实际安装目录加载能力。远端数据执行端需自行准备实际知识根、解释器与依赖，并通过宿主已配置的 SSH 能力运行 CLI。

开发测试统一位于 [evals/deploy/](../../evals/deploy/)，通过 [evals 运行器](../../evals/README.md#执行) 的 `--groups deploy` 执行。测试使用临时目录、模拟依赖安装、模型准备和解释器记录器，验证准备顺序、离线模型完整性、损坏集合处理、失败保留旧包、三路包替换、项目文件保持原样及平台入口参数传递。日常操作见[使用说明](../../docs-llm-wiki/使用说明.md)。
