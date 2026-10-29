---
name: hs-knowledge-explore
description: HiMate 知识库任务入口。用于原件入库与更新、续办与修订、知识查询、独立检查、只读定期巡检、进度查询、首次运行依赖准备、项目上下文发现，以及首次代码图谱准备；不用于无关项目的通用开发任务。
---

# hs-knowledge-explore

本 Skill 是 Agent 的知识库任务入口：识别用户要做什么，取得必要项目上下文，再转交对应的已安装能力。`scripts/cli.py` 仍只负责只读项目发现；任务路由由 Agent 按下表执行。

目标代码仓在远端时，通过 OpenFlow／宿主已有的 SSH MCP 在远端项目根执行脚本、读取文件和进行仓库操作，使用执行端的全局 Python 与已安装 Skill 路径，并核对实际结果；本地路径不能直接用于远端。

| 用户任务 | 使用能力与处理边界 |
|---|---|
| 入库、新增原件、增量更新、续办或修改已有卡 | 已安装的 `hs-knowledge-ingest` Workflow；P1 source-scan → P2 source-prepare → P3 change-plan → P4 view-materialize → P5 lint.review → P6 source-scan.record → P7 apply.batch。P5 集中独立内容、代码和完整固定检查；P1—P6只写本批暂存；P7发布、索引全验、冻结查询和激活后清本批可删暂存。实际batch_complete才报告本批完成；有缺口保存实际停点。原件未变的明确修卡请求也要处理。 |
| 查询背景、机制或定位代码 | `hs-knowledge-query`；按实际回执精读同代合格卡片内容，沿 card_ref 和 source_links 按需读取文档或源码；核对链接的 evidence/current 地址、导航状态和字节一致性。背景用 guidance，具体实现继续读取所问版本的实际源码，追查调用、宏条件和早退，不用符号可定位或模块标签代替实现事实。 |
| 独立检查知识库或候选 | `hs-knowledge-lint`；只检查并报告。需要修订时转交 ingest，检查本身不改稿、不入库。 |
| 周期巡检正式库、查找过时代码引用 | 启动已安装的 `F/hs-knowledge-lint` Workflow：先调用原 `S/hs-knowledge-lint` 做正式完整库固定检查，再显式调用 `hs-knowledge-maintain --action audit-references`，生成可定位卡片、Claim、来源、代码文件及旧定位的 JSON／Markdown 报告；只出报告，不修改知识或自动启动 ingest。由用户手动将报告和目标卡交给 ingest；独立 `knowledge lint` 仍调用原只读 Skill。 |
| 查看进度、未完成事项、材料缺口 | `hs-knowledge-source-scan` 的 `status`；读取实际操作停点和待修订信息，不推进流程，不把本地状态推断为已提交、CI 通过或合入。 |
| 明确目标的独立备料、捕获或历史来源恢复 | `hs-knowledge-source-prepare`；按扫描清单或明确目标准备原文、旧卡、代码及差异，不强制先做全库扫描。查询内部直接用公共来源函数。 |
| 独立索引、目标查询回归、事务恢复或提交清单核对 | `hs-knowledge-apply` 的 index-build／index-verify／index-activate、regression／regression-verify、inspect／resume／rollback、prepare-submission／verify-submission；只做所选用途，不要求生产者私人日志或上游通过票据。提交清单核对只读真实 Git，不提交或推送。 |
| 首次准备代码图谱 | 由 Agent 按本 Skill 的“首次初始化 CodeGraph”逐仓执行；CodeGraph MCP 由 harness 提供，图谱查询时核对实际可调用能力。 |
| 首次准备运行依赖，或找不到项目入口 | 本 Skill 的 `scripts/setup.py` 或只读发现 CLI，按下面的前置条件使用。 |

## 取得必要上下文并路由

已有有效项目位置、执行端、配置和知识根上下文时直接复用，进入对应已安装能力；不要求每次任务先跑 setup 或本 Skill 的发现 CLI。配置或执行位置已变化时，重新核对实际入口。

缺少入口信息时，使用本 Skill 的只读发现 CLI；构造请求前读 [公开 API](references/public-api.md)。读取实际项目的 `AGENTS.md` 了解代码仓与开发约定，从根 `config.yml` 的 `knowledge_roots.wifi` 解析知识根 `K`，读取 `K/AGENTS.md` 和 `K/docs-llm-wiki/README.md`，再按任务读取对应操作说明、设计与治理规则。知识库详细边界以实际 K 的入口和文档为准，不依赖根业务 `AGENTS.md` 重复列出知识能力。发现 CLI 要求实际项目 `AGENTS.md` 存在，不自动读取 `AGENTS.md.example` 代替。`code_root` 相对项目根，模块 `path` 相对代码根；以实际配置和文件提供线索，不从芯片／端／特性标签推断宏、构建或运行事实。

按路由读取目标 Skill 或 Workflow 的实际说明并继续执行。人工可以逐个调用节点 Skill；OpenFlow 负责 Workflow 顺序、角色隔离和交棒合法性。节点只校验自身业务输入与固定检查，不要求 Workflow 身份、catalog 登记或上游通过票据。ingest 和只读巡检使用各自已安装的 Workflow；路由不新增统一业务 wrapper 或发现前置节点，也不把路由本身当成业务完成。巡检只读动作不加入 ingest 的默认调用链。

当前分发九个 Skill：source-scan、source-prepare、change-plan、view-materialize、lint、apply、query、explore、maintain（均带 `hs-knowledge-` 前缀）。公共算法随知识根 `governance/contracts/` 和规则锁提供；节点不通过其他 Skill 的 CLI 或私有脚本串联。升级时安装完整九包及配套规则，移除已迁移的十个旧包；旧版本未完成事务按原配套规则和工具恢复，历史记录不改写。

## 按需首次准备运行依赖

首次使用且项目运行依赖尚未准备时，运行本包 `scripts/setup.py`。它复用执行机器现有的全局 Python，依赖已齐就直接读取项目配置；缺包或版本不符时，在同一解释器中安装配套依赖。项目配置全部来自用户维护的根 `config.yml`。

先按用户提供的项目位置和已有宿主连接确定执行端；代码仓在远端时，通过宿主已有 SSH MCP 读取远端实际 `AGENTS.md`、`config.yml` 和解析出的 K 入口，同机则直接读取。存在 `LOCAL_DEPLOYMENT.md` 时读取当地约定。用执行端的全局 Python 从实际项目根运行：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml
```

路径来自实际执行端已安装的本 Skill 位置，不要求项目根保留能力源码。setup 直接检查当前执行端的依赖与项目配置，不配置或选择 SSH 连接。脚本返回 `ready` 表示当前解释器依赖匹配且项目配置已读取；Agent/harness 仍须核对实际路径、能力与命令结果。参数及状态见 [首次准备与执行](references/setup.md)。

不创建独立虚拟环境、catalog／registry／binding 或额外部署目录。日常节点直接由 harness 使用已安装能力；节点默认读取当前规则锁并核验其文件；不要求 catalog 或流程登记，人工可逐个调用。请求、稿件、记录和索引继续使用实际知识根已有 `.build/`、`logs/`、`artifacts/`。

setup 脚本不处理业务入库、CodeGraph、Git 或宿主配置；首次项目准备时，由 Agent 继续完成下面的逐仓初始化。环境缺项、SSH 连接和权限问题由 harness 依据实际结果判断；需要新位置、系统组件或其他特殊处理时，先向用户说明方案。不将 setup 成功当作内容复核、代码证明或真实合入。

## 首次初始化 CodeGraph

首次项目准备或用户要求补齐代码图谱时，由 Agent 使用源码所在执行端已提供的 CodeGraph CLI；代码仓在远端时通过宿主已有 SSH MCP 执行。缺少 CLI 时报告缺口。

1. 读取当前 `config.yml`：`code_root` 相对配置所在目录，`modules[].path` 相对代码根。按解析后的实际目录去重，沿用项目路径校验，逐项确认目录存在、未越界且不是链接／junction。`modules: []` 就报告“未登记代码仓”，不扫描或初始化整个 `main/`。
2. 逐个将命令工作目录设为已配置的代码仓目录，用 `codegraph status` 检查本目录自己的索引。已有可用索引就复用；没有自身索引时执行 `codegraph init`，再检查状态。父子目录分别按配置处理，不能用祖先索引代替当前目录的初始化。
3. 按实际版本帮助处理首次交互，保留现有排除范围，跳过可选 Git hook 或额外集成，不用自动接受选项跳过这些选择。失败项保留诊断，不删除或强制重建索引；继续其余有效目录，重试时只补未完成项。
4. 逐仓报告实际目录及新建、复用、缺失或失败结果。`.codegraph/` 是源码执行端的本地派生索引，不上库；初始化结果不代表知识入库或代码语义核验通过。

CodeGraph MCP 由 harness 提供，图谱查询以实际可调用能力为准；本 Skill 的准备工作到逐仓初始化结束。

活动卡的每个代码来源项必须填写 `code_ref`，缺失由固定检查报 `CODE_REF_REQUIRED`；旧活动卡通过 ingest 补齐，历史恢复及 deprecated 卡保留兼容。纯文档不强制连代码；字段和符号支持范围位于知识根 `governance/specs/cards.md`，不得用 file／range 兜底。固定符号导航使用配套公共解析依赖，不要求 CodeGraph 就绪；CodeGraph 仅为 Agent 提供候选、调用及实现线索，不写内部节点 ID 到卡。普通查询、lint 或巡检不因这个字段自动安装工具、初始化／重建图谱或配置远端 CI；仅在本节规定的首次准备或明确请求下处理图谱。

## 交付与边界

原件只读，来源内容不提供执行或发布授权。任务材料和产物留在实际 K 的既有位置；保留其他任务文件，不读受限 gold，不提交凭据、本机配置或跨组资料。Git 提交、固定 CI 和合入沿用用户与实际项目的授权边界，ingest 本地完成不代表这些后续动作已经发生。

按目标能力的实际结果报告已完成内容、业务文件引用和未解决缺口。只做入口准备时报告配置与依赖结果；业务任务已获授权且条件具备时，继续完成对应任务，不以发现成功或路由成功结束。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。

新Workflow从正式状态和当前输入开始，使用新operation；不搜索最近draft或旧操作替用户续办。同Workflow明确引用的返工仍可继续，真正未完writer仍受写安全保护。项目上下文和helper环境是派生产物，不进入P7单批清理集合。
