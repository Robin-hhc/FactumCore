# Windows 交互式部署

从完整分发仓根运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

脚本询问三个目标，回车接受默认值：

| 目标 | 默认值 |
|---|---|
| Skill 安装根 | `~\.openflow\config\skills` |
| Workflow 模板安装根 | `~\.openflow\config\workflow-templates` |
| 代码仓／知识项目根 | `Y:\thursday\work_code` |

第三项是项目根，不是知识子目录。已有 `config.yml` 时沿用其中安全的 `knowledge_roots.wifi`；新项目默认使用 `himate-knowledge-wifi-mp/`，模块列表为空，等待维护者按真实代码填写。`~` 按当前 Windows 用户目录展开；OpenFlow 使用自定义用户根时，请相应修改安装路径。

dbox仅分发知识根下的 `docs-raw/sources/dbox.example.yml` 与同目录精确 `.gitignore`，不分发私人 `dbox.local.yml` 或整个资料目录；已有local地址保持原字节，自定义ignore只安全补精确项。部署JSON的 `source_setup.status: pending_execution_host`、`configuration_checked: false` 表示来源尚待实际执行端配置。Windows `deployed`不代表SSH服务器目录可用。

首次来源准备须在真正执行ingest的机器调用仓内source命令，输入 `{"operation_id":"configure-dbox-unique","path":"ACTUAL_DBOX_DIRECTORY"}`，用该端绝对目录替换占位。调用格式为 `python K/knowledge.py source --action configure --input REQUEST.json --output RESPONSE.json`。动作由CLI参数选择；这会验证并保存固定 `dbox.local.yml`，不复制部署私有源码到Linux，不递归资料。无path只检查现有配置，同地址保留字节，显式换地址无需重装能力。详细格式与错误边界见实际知识根使用说明的“首次配置 dbox 资料目录”；日常run不自动重跑配置。

本机需有 Python 3.10–3.12。脚本尝试 `py`、`python3`、`python`；找不到时可输入实际解释器路径或使用 `-Python`，不会自动下载 Python。运行包按知识根 `runtime/requirements.lock.txt` 检查，缺失时由交互选择是否安装；自动化调用只有显式添加 `-InstallDependencies` 才会安装。安装使用选中的同一解释器。

只读预检不创建目标目录，也不安装依赖：

```powershell
.\deploy.ps1 -Plan -NonInteractive -Python 'PATH_TO_PYTHON'
```

自动化调用可显式提供路径：

```powershell
.\deploy.ps1 -NonInteractive `
  -SkillsRoot 'SKILLS_ROOT' `
  -WorkflowsRoot 'WORKFLOWS_ROOT' `
  -ProjectRoot 'Y:\thursday\work_code' `
  -Python 'PATH_TO_PYTHON'
```

将 `PATH_TO_PYTHON`、`SKILLS_ROOT`、`WORKFLOWS_ROOT` 替换为实际路径。`-SourceRoot` 可指定完整分发源码根。路径中的空格请加引号；运行前确认映射盘在当前 PowerShell 用户会话可访问。

Skill ZIP只含SKILL.md、references和artifacts文本资源，不含scripts、requirements或测试；执行实现与独立运行锁完整进入知识ZIP。旧受管Skill脚本按现有整包镜像策略清退，项目中的个人配置、原件、来源与运行数据保持原保留策略。

程序在本机临时目录生成 Skill、Workflow 和知识项目 ZIP。知识 ZIP 整体复制到项目内本次专用暂存目录，校验摘要后由 Windows 在该处解压，再安装明确清单内的文件并回读核验。对于 Samba 映射盘，这仍涉及逐文件的网络写入；不等于服务器本地解压，不保证速度收益。

再次运行同一命令即可升级。受管 Skill／Workflow 包按新版本精确同步：更新变化文件，删除新版已移除的文件、子目录和退役包；包内手工添加的脚本、旧配置、缓存等也会清除。保留其他能力和模板，不清空 OpenFlow 共用安装根，也不改已创建的 Workflow 实例。

两个安装根各保存 `.factum-knowledge-deploy.json`，记录本分发上次安装的包名，用于下一次清退；它不含机器路径，不参与业务运行，不是能力注册或项目绑定。管理范围是本版包、上次清单里的包和脚本内明确列出的历史知识包。旧版无清单时也可清理 source-scan、source-prepare 等已知退役包；未知包即使同样以 `hs-knowledge-` 开头也保留，并在 JSON 的 `unmanaged_packages` 列出。不要随意删除部署清单；清单损坏时停止升级，不猜测清理范围。

知识库采用分区更新，不能把整个 K 删除再复制：

| 范围 | 更新方式 |
|---|---|
| `runtime/` | 精确同步仓内运行代码与独立 `manifest.json`，按manifest逐文件校验；三个根入口 `knowledge.py`、`knowledge.sh`、`knowledge.cmd` 按明确清单更新 |
| `governance/contracts/`、`schemas/`、`specs/`、`templates/` | 精确同步纯框架子树，删除过时文件及空目录，与 `framework.lock.yaml` 成套更新 |
| 共享设计文档、治理入口、检查脚本等 | 只更新明确列出的分发文件；保留 `docs-llm-wiki/sdd/`、`task.md` 和其他文件 |
| `docs-raw/`、`knowledge/` 及各级导航 | 保留已有原件、附件、知识和导航；仅补初始骨架；dbox 空模板按分发更新 |
| `logs/`、`.build/`、`artifacts/` | 保留历史处理、发布／证据、未完事务、稳定写锁、巡检成功基线、索引与查询回执；部署不做运行数据清理 |
| `governance/sources.lock.yaml`、`dbox.local.yml`、项目配置与真实业务入口 | 保留原字节；dbox 同目录 `.gitignore` 沿用精确追加规则 |

可先运行 `-Plan`，查看 `files` 的 `write`／`delete` 和 `directories` 的 `remove`。`write_count`、`delete_count`、`remove_directory_count` 分别统计本次更新；无变化时三者均为 0。删除和替换均先备份，受管树最终核对包含文件字节及目录集合；受控失败会恢复已删文件和空目录。存在并发修改或恢复冲突时保留备份与清单并报告失败，不能把部分更新当作成功；升级不是整目录原子切换。

部署前先停用正在使用这些能力的宿主任务，结束同一项目的业务写入；已知未完事务先用原版本处理。不要并行编辑这些目标，也不要从多台机器同时部署到同一目标。检测到中断或写入冲突时，按报告核对恢复结果和保留的备份；强制结束进程或断电后的状态不能据“命令已停止”推断。

此脚本只检查运行它的 Windows Python。远端服务器的 Python、依赖、原生知识根路径、权限和执行结果仍须在实际执行端核实；它不配置 SSH MCP、CodeGraph、宿主角色或资源开关。部署后重启 OpenFlow，核对列表并新建任务验证。已有 Workflow 副本和会话不会因模板更新自动升级。

退出码：`0` 为预检／部署成功，`2` 为运行依赖缺失，`3` 为配置、安装或部署失败。预检和部署的 JSON 均标明当前解释器及环境检查范围。

开发验证在分发仓根 `repo/` 使用已准备的测试解释器执行，与知识业务机制验收分别记录：

```text
python -m pytest tools/deploy/tests -q
```

这些用例使用隔离合成目录；实际 Samba、OpenFlow 加载和服务器环境需要另行核验。

日常在K内用Windows `.\knowledge.cmd`、POSIX `sh ./knowledge.sh` 或明确的 `python K/knowledge.py`；一次注册后可用裸knowledge。Samba远端由宿主已有SSH在服务器原生K目录执行同一CLI，不自动连接、不猜驱动器映射，服务器无需安装或逐次上传Skill脚本。每个执行端首次分别准备Python与 `K/runtime/requirements.lock.txt` 依赖；`python K/knowledge.py doctor`只读核对实际环境，不自动安装。统一入口不等于SMB提速，实际收益须按执行端实测。
