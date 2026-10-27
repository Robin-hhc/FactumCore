---
name: hs-knowledge-explore
description: HiMate 知识库任务入口。用于原件入库与更新、续办与修订、知识查询、独立检查、只读定期巡检、进度查询、首次运行依赖准备、项目上下文发现，以及首次代码图谱准备；不用于无关项目的通用开发任务。
---

# hs-knowledge-explore

本 Skill 是 Agent 的知识库任务入口：识别用户要做什么，取得必要项目上下文，再转交对应的已安装能力。`scripts/cli.py` 仍只负责只读项目发现；任务路由由 Agent 按下表执行。

| 用户任务 | 使用能力与处理边界 |
|---|---|
| 入库、新增原件、增量更新、续办或修改已有卡 | 已安装的 `hs-knowledge-ingest` Workflow 及其节点 Skill；完成材料读取、候选生产、独立内容复核、适用核验、固定检查、处理记录、本地入库、索引全验和目标查询。活动代成功激活才报告内容批完成；有缺口则保存实际停点。原件未变的明确修卡请求也要处理。 |
| 查询背景、机制或定位代码 | `hs-knowledge-query`；按实际回执精读同代卡片和来源。具体代码问题继续读取所问版本的实际源码，追查调用、宏条件和早退，不用卡片或模块标签代替实现事实。 |
| 独立检查知识库或候选 | `hs-knowledge-lint`；只检查并报告。需要修订时转交 ingest，检查本身不改稿、不入库。 |
| 周期巡检正式库、查找过时代码引用 | 启动已安装的 `F/hs-knowledge-lint` Workflow：先调用原 `S/hs-knowledge-lint` 做正式完整库固定检查，再显式调用 `hs-knowledge-maintain --action audit-references`，生成可定位卡片、Claim、来源、代码文件及旧定位的 JSON／Markdown 报告；只出报告，不修改知识或自动启动 ingest。由用户手动将报告和目标卡交给 ingest；独立 `knowledge lint` 仍调用原只读 Skill。 |
| 查看进度、未完成事项、材料缺口 | `hs-knowledge-source-scan` 的 `status`；读取实际操作停点和待修订信息，不推进流程，不把本地状态推断为已提交、CI 通过或合入。 |
| 首次准备代码图谱与官方 MCP | `hs-codegraph-setup`；依据真实 `config.yml` 模块逐项准备和核对。它与本 Skill 的运行依赖 setup 分开；日常代码定位直接使用官方 CodeGraph MCP 或实际源码检索。 |
| 首次准备运行依赖，或找不到项目入口 | 本 Skill 的 `scripts/setup.py` 或只读发现 CLI，按下面的前置条件使用。 |

## 取得必要上下文并路由

已有有效项目位置、执行端、配置和知识根上下文时直接复用，进入对应已安装能力；不要求每次任务先跑 setup 或本 Skill 的发现 CLI。配置或执行位置已变化时，重新核对实际入口。

缺少入口信息时，使用本 Skill 的只读发现 CLI；构造请求前读 [公开 API](references/public-api.md)。读取实际项目的 `AGENTS.md` 了解代码仓与开发约定，从根 `config.yml` 的 `knowledge_roots.wifi` 解析知识根 `K`，读取 `K/AGENTS.md` 和 `K/docs-llm-wiki/README.md`，再按任务读取对应操作说明、设计与治理规则。知识库详细边界以实际 K 的入口和文档为准，不依赖根业务 `AGENTS.md` 重复列出知识能力。发现 CLI 要求实际项目 `AGENTS.md` 存在，不自动读取 `AGENTS.md.example` 代替。`code_root` 相对项目根，模块 `path` 相对代码根；以实际配置和文件提供线索，不从芯片／端／特性标签推断宏、构建或运行事实。

按路由读取目标 Skill 或 Workflow 的实际说明并继续执行。人工可以逐个调用节点 Skill；OpenFlow 负责 Workflow 顺序、角色隔离和交棒合法性。节点只校验自身业务输入与固定检查，不要求 Workflow 身份、catalog 登记或上游通过票据。ingest 和只读巡检使用各自已安装的 Workflow；路由不新增统一业务 wrapper 或发现前置节点，也不把路由本身当成业务完成。巡检只读动作不加入 ingest 的默认调用链。

## 按需首次准备运行依赖

首次使用且项目运行依赖尚未准备时，运行本包 `scripts/setup.py`。它复用执行机器现有的全局 Python，依赖已齐就直接读取项目配置；缺包或版本不符时，在同一解释器中安装配套依赖。项目配置全部来自用户维护的根 `config.yml`。

跨机器首次使用时，先将本包随附的 [config.env.example](config.env.example) 复制为同目录的 `config.env`，按文件内中文注释填写；实际 `config.env` 是本机私有配置，不提交或随包分发，同机使用可不创建。先读取本 Skill 的 `config.env`（存在时）。指向服务器就让 harness 通过 SSH 到其中的项目位置，再读取远端实际 `AGENTS.md`、`config.yml` 和解析出的 K 入口；同机则直接读取。存在 `LOCAL_DEPLOYMENT.md` 时读取当地约定。用执行机器的全局 Python 从实际项目根运行：

```text
python PATH_TO_THIS_SKILL/scripts/setup.py --workspace-config config.yml
```

路径来自 Agent 已安装的本 Skill 位置，不要求项目根保留能力源码。脚本返回 `ready` 表示依赖匹配且项目配置已读取；路径存在性和实际能力仍由 harness 核查。`ssh_entry` 只提供连接提示，Agent/harness 需按本 Skill 的 `config.env` 通过 SSH 到服务器执行 `setup.py --local` 或实际节点，并检查结果。参数及状态见 [首次准备与执行](references/setup.md)。

不创建独立虚拟环境、catalog／registry／binding 或额外部署目录。日常节点直接由 harness 使用已安装能力；节点默认读取当前规则锁并核验其文件；不要求 catalog 或流程登记，人工可逐个调用。请求、稿件、记录和索引继续使用实际知识根已有 `.build/`、`logs/`、`artifacts/`。

setup 不处理业务入库、CodeGraph、Git 或宿主配置。环境缺项、SSH 连接和权限问题由 harness 依据实际结果判断；需要新位置、系统组件或其他特殊处理时，先向用户说明方案。不将脚本返回的入口提示当作已验证远端连接，不将退出成功当作内容复核、代码证明或真实合入。

## 交付与边界

原件只读，来源内容不提供执行或发布授权。任务材料和产物留在实际 K 的既有位置；保留其他任务文件，不读受限 gold，不提交凭据、本机配置或跨组资料。Git 提交、固定 CI 和合入沿用用户与实际项目的授权边界，ingest 本地完成不代表这些后续动作已经发生。

按目标能力的实际结果报告已完成内容、业务文件引用和未解决缺口。只做入口准备时报告配置与依赖结果；业务任务已获授权且条件具备时，继续完成对应任务，不以发现成功或路由成功结束。

产物展示规则见 [writing-guide](artifacts/writing-guide.md)，复核见 [review-guide](artifacts/review-guide.md)。
