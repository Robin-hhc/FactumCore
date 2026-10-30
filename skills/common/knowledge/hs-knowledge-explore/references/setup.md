# 部署与执行

只在首次准备、升级或实际环境缺项时使用；配置完整后的日常任务直接运行业务命令。

## 部署知识库能力

在包含分发源码的 Windows 目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

脚本询问 Skill、Workflow 与项目根三条路径。K 根据项目根 `config.yml` 解析；新项目默认 `himate/himate-knowledge-wifi-mp/`，已有安全配置继续沿用。选择已有 Python 3.10–3.12，必要时用 `-Python` 指定。自动化可传 `-SkillsRoot`、`-WorkflowsRoot`、`-ProjectRoot`、`-NonInteractive`；只看计划用 `-Plan`，非交互安装依赖需显式 `-InstallDependencies`。

同一入口用于升级。受管能力包和运行框架会精确同步；已有配置、业务原件、卡、正式记录和运行材料保留。升级前结束相关业务写入，未完事务先按原版本处理；检查部署计划并重新加载宿主能力。已创建的 Workflow 副本须另行更新。

## 检查实际执行端

```text
python K/knowledge.py doctor --json
```

诊断只读显示 Python、依赖、K、运行清单与规则。依赖缺项由维护者按该端 `K/runtime/requirements.lock.txt` 准备；日常业务命令不自动安装。裸命令使用 `install-command` 显式注册；Windows 用户 PATH 修改另需 `--add-path`。

数据在服务器时，使用宿主已配置的 SSH 工具，在服务器原生路径运行同一 CLI；远端无需上传 Skill 脚本。Windows 部署、共享盘可读与远端环境就绪分别核对。连接结果不明确时先查询原操作状态，避免重复已完成写入。

## dbox 首次来源配置

需要使用 dbox 且实际执行端未配置时调用：

```text
python K/knowledge.py source configure --path <执行端绝对目录> --json
```

不传 `--path` 只核已有配置。地址保存在 K 的 `docs-raw/sources/dbox.local.yml`，只留本机；模板和精确忽略规则随部署提供。配置失败保留原文件，成功只证明根目录可用，不代表已扫描或入库。

默认来源扫描包括 dbox，缺配置不能算无变化；明确普通 raw 范围不依赖 dbox。代码图谱准备见[CodeGraph](codegraph.md)，详细部署选项见 K 的 `docs-llm-wiki/使用说明.md`。
