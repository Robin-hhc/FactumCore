# 部署与执行

## Windows 部署入口

首次安装或本机依赖缺项时，在包含分发源码和 `deploy.ps1` 的 Windows 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy.ps1
```

脚本询问 Skill、Workflow 和知识项目根三条路径。第三条是项目根，不是知识根：已有 `config.yml` 时沿用其中 `knowledge_roots.wifi`，允许安全嵌套；没有配置时使用项目根下的 `himate-knowledge-wifi-mp/`。完整默认值、参数和保留策略见实际知识根 `docs-llm-wiki/使用说明.md` 的“首次环境安装”。

脚本选择本机已有 Python 3.10–3.12；找不到时由用户先安装，或用 `-Python` 指定实际解释器，不自动下载 Python。默认核对该解释器的K/runtime/requirements.lock.txt 运行锁，交互模式发现缺包时询问是否修复；非交互修复须显式提供 `-InstallDependencies`。安装和后续部署使用同一个解释器。只看计划使用 `-Plan`，自动化可显式指定 `-SkillsRoot`、`-WorkflowsRoot`、`-ProjectRoot` 和 `-NonInteractive`。

三份 ZIP 在本机临时生成；知识 ZIP 整体复制到项目根内本批暂存位置，再由 Windows 直接在目标路径解压并逐文件回读核对 SHA-256。映射共享盘仍有小文件写入开销，这不代表服务器本地解压，也不证明服务器 Python 或依赖可用。

再次运行同一命令即可升级。受管能力包精确同步并清除过时文件／退役包，包内手工新增内容也会删除；安装根的 `.factum-knowledge-deploy.json` 只记上次部署包名，不参与业务运行。未知包即使同前缀也保留；无清单的旧部署仅接管本版与已知历史包，不清空共用安装根。

知识库精确同步 `runtime/` 仓内实现与独立manifest，并更新三个knowledge启动入口；Skill只分发文本指引及契约，不分发scripts或requirements。治理的 `governance/{contracts,schemas,specs,templates}/` 四个纯框架子树与 `framework.lock.yaml` 成套更新；共享文档按明确文件清单替换，不清空整个治理或文档目录。已有项目配置、根 `AGENTS.md`、原件、卡及导航、来源锁、dbox 私人配置、全部日志、`.build/`、`artifacts/` 与本机文档保留。不要把“不上库”或“可重建”当作允许部署清空。

升级前停用相关宿主任务、结束业务写入，已知未完事务先用原版本处理；可用 `-Plan` 核对更新／删除／目录移除计划。受控失败尝试回滚，冲突则保留备份并报告失败。脚本不改宿主 SSH／MCP／权限开关，不安装或初始化 CodeGraph。完成后重启 OpenFlow、核对能力列表，并用新任务验证；已有 Workflow 副本不自动升级。

## dbox 首次来源配置

部署仅精确分发K下的 `docs-raw/sources/dbox.example.yml` 和同目录 `.gitignore`，保留已有 `dbox.local.yml` 地址，安全补齐忽略项。部署结果中的 `source_setup.status: pending_execution_host`、`configuration_checked: false` 与 deployed 分开，不能据Windows本机或映射盘可读声称SSH服务器来源就绪。

首次须在真正执行ingest的机器调用仓内 `python K/knowledge.py source --action configure --knowledge-root K --input REQUEST.json --output RESPONSE.json`，独立请求例如 `{"operation_id":"configure-dbox-unique","path":"ACTUAL_DBOX_DIRECTORY"}`。动作由CLI参数选择；用执行端绝对目录替换占位，配置保存为 `schema_version: '1.0'` 与一个path。Linux复用此公开动作，不复制私有部署源码或新建runner。无path只核现有配置，同地址保留字节，显式换目录无需重装能力；目录、Git忽略保护或写前旧基线有误不覆盖旧配置。非Git工作区不虚报忽略已验证。

configure只核根、不递归资料，成功不代表全目录完整或已入库。默认全量scan包含六类raw和dbox逻辑根，缺配置、根不可达或读失败不能假称无变化；限定普通raw范围不检查无关dbox。日常业务不自动重跑configure/setup，不跟随原生链接或调用平台API。已发布的确切原文可独立于生产者私人地址恢复。

## 日常项目发现

已有部署和有效项目上下文时，直接按 [任务入口](../SKILL.md) 使用业务能力。缺少上下文才调用 [只读发现 CLI](public-api.md)，读取真实 `AGENTS.md`、`config.yml`、K 入口及所需规则；发现过程不安装包、不登记能力，也不生成业务处理义务。

`repo/` 表示实际业务工作区，`K` 是其 `config.yml` 解析出的知识根，`S`、`F` 是实际已安装能力目录。原件、卡、治理及运行产物沿用 K 的现有布局；请求和稿件在 `.build/`，正式记录在 `logs/`，索引和报告在 `artifacts/`。

## 远端任务与代码图谱

目标代码仓在远端时，先由用户或部署维护者在 OpenFlow 配置、启用并验证 SSH MCP，让需要远端执行的角色可调用它。Agent 通过该 MCP 在实际远端项目根执行业务脚本和仓库操作，另核对该端 Python、配套依赖和仓内 CLI 路径。Windows 部署脚本不建立 SSH 连接，本机检查结果不能代替执行端检查。

SSH 结果不明或连接中断时，先核对原执行端进程、操作记录、journal 和活动代，再决定续办；不推断远端未执行，也不重复已提交写入。

CodeGraph 仍按 [首次初始化 CodeGraph](../SKILL.md#首次初始化-codegraph) 由 Agent 使用源码所在端已有 CLI 逐仓处理；已有索引复用，空模块列表不建图。MCP 由宿主提供，缺项如实报告。部署完成不代表 CodeGraph、Workflow 调度或知识业务验收通过。

## 执行端诊断与一次依赖准备

在真正执行任务的机器调用：

```text
python K/knowledge.py doctor
```

doctor只读显示该端Python、知识根、配套运行manifest、治理规则和缺失依赖；不安装、不扫描原件、不建索引。首次依赖准备或升级由维护者按 `K/runtime/requirements.lock.txt` 在当前执行机完成，不共享Windows与Linux的解释器或虚拟环境；日常命令不自动联网安装。旧开发setup不随Skill分发，也不是远端前置。

Windows在K目录使用 `.\knowledge.cmd`，POSIX使用 `sh ./knowledge.sh`，也可明确用该端Python运行 `K/knowledge.py`。裸 `knowledge` 需要显式运行install-command并按返回说明准备本机PATH；注册只建立本机轻量入口，不绑定所有项目到某个知识根。执行实现随知识仓同步后，SSH端无需再传Skill脚本。脚本仍从Windows映射盘运行时仍有SMB开销；应在数据所在端的原生路径运行，实际收益另行实测。
