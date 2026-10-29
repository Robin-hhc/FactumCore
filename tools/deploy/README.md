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

本机需有 Python 3.10–3.12。脚本尝试 `py`、`python3`、`python`；找不到时可输入实际解释器路径或使用 `-Python`，不会自动下载 Python。运行包按 explore 的锁定清单检查，缺失时由交互选择是否安装；自动化调用只有显式添加 `-InstallDependencies` 才会安装。安装使用选中的同一解释器。

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

程序在本机临时目录生成 Skill、Workflow 和知识项目 ZIP。知识 ZIP 整体复制到项目内本次专用暂存目录，校验摘要后由 Windows 在该处解压，再安装明确清单内的文件并回读核验。对于 Samba 映射盘，这仍涉及逐文件的网络写入；不等于服务器本地解压，不保证速度收益。

更新保留业务配置、已有业务入口、原件、知识卡、导航、来源锁及正式记录；治理代码和规则锁成套部署。发现写入冲突或校验失败时报告实际结果，不能把部分部署当作成功。用户其他 Skill、Workflow 和未知文件不自动删除。

部署前先结束同一项目的业务写入，不要并行编辑这些目标，也不要从多台机器同时部署到同一目标。检测到中断或写入冲突时，按报告核对恢复结果和保留的备份；强制结束进程或断电后的状态不能据“命令已停止”推断。

此脚本只检查运行它的 Windows Python。远端服务器的 Python、能力路径、权限和执行结果仍须在实际执行端核实；它不配置 SSH MCP、CodeGraph、宿主角色或资源开关。部署后重启 OpenFlow，核对列表并新建任务验证。已有 Workflow 副本和会话不会因模板更新自动升级。

退出码：`0` 为预检／部署成功，`2` 为运行依赖缺失，`3` 为配置、安装或部署失败。预检和部署的 JSON 均标明当前解释器及环境检查范围。

开发验证在分发仓根 `repo/` 使用已准备的测试解释器执行，与知识业务机制验收分别记录：

```text
python -m pytest tools/deploy/tests -q
```

这些用例使用隔离合成目录；实际 Samba、OpenFlow 加载和服务器环境需要另行核验。
