---
name: hs-knowledge-explore
description: HiMate 知识库任务入口。用于原件入库与更新、续办与修订、知识查询、独立检查、只读定期巡检、进度查询、项目上下文发现、部署与依赖问题指引，以及首次代码图谱准备；不用于无关项目的通用开发任务。
---

# hs-knowledge-explore

执行入口为实际知识根的 `python K/knowledge.py explore`；在 K 目录内 Windows 可用 `.\knowledge.cmd explore`，POSIX 可用 `sh ./knowledge.sh explore`。完成一次命令注册后可使用裸 `knowledge`。复杂请求保留 `--input/--output`；省略根、操作标识和输出路径时由 CLI 固定并返回实际引用。本 Skill 仅提供任务方法和产物契约，执行实现与依赖锁随 K/runtime 分发。

本 Skill 是 Agent 的知识库任务入口：识别用户要做什么，取得必要项目上下文，再转交对应的已安装能力。仓内 `python K/knowledge.py explore` 只负责只读项目发现；任务路由由 Agent 按下表执行。

本机数据使用本机知识根 K 的仓内 CLI。代码仓在服务器或 Windows 仅经 Samba 映射访问时，通过 OpenFlow／宿主已有 SSH MCP 在服务器原生 K 路径运行 CLI 并核对实际结果；不自动连接 SSH，不推断映射关系。本机与服务器分别准备 Python 和配套依赖，远端不需要安装或上传 Skill 脚本。

| 用户任务 | 使用能力与处理边界 |
|---|---|
| 入库、新增原件、增量更新、续办或修改已有卡 | 已安装的 `hs-knowledge-ingest` Workflow；prepare_sources使用source默认run同进程完成P1观察和P2备料，再交P3 change-plan → P4 view-materialize → P5 lint.review → P6 source.record → P7 apply.batch，共6个调度节点。真正无变化在来源节点结束；退回补料只用source.prepare，不先重扫。P5独立审阅及完整检查；P1—P6只写本批暂存，P7发布、检索收尾并清本批可删暂存。实际batch_complete才报告完成，原件未变的明确修卡同样处理。 |
| 查询背景、机制或定位代码 | `hs-knowledge-query`；按实际回执精读同代合格卡片内容，沿 card_ref 和 source_links 按需读取文档或源码；核对链接的 evidence/current 地址、导航状态和字节一致性。背景用 guidance，具体实现继续读取所问版本的实际源码，追查调用、宏条件和早退，不用符号可定位或模块标签代替实现事实。 |
| 独立检查知识库或候选 | `hs-knowledge-lint`；只检查并报告。需要修订时转交 ingest，检查本身不改稿、不入库。 |
| 周期巡检、未入库raw、登记代码变更 | 启动已安装的 `F/hs-knowledge-lint` Workflow：maintain 独立同步后重新载入规则，脚本生成差异与精确 source_request，复用 source.prepare 和 ingest P3—P7处理；实际完成后才推进成功基线，失败与欠账保留。只检查直接登记文件；同步命令由控制端显式配置。独立 `knowledge lint` 仍调用只读 Skill，单纯引用报告可调用 maintain.audit-references。 |
| 查看进度、未完成事项、材料缺口 | `hs-knowledge-source` 的 `status`；读取实际操作停点和待修订信息，不推进流程，不把本地状态推断为已提交、CI 通过或合入。 |
| 明确目标的独立备料、捕获或历史来源恢复 | `hs-knowledge-source`的prepare／capture／resolve／resolve-source；按固定清单或明确目标处理原文、旧卡、代码及差异，不强制先scan或run。仅观察变化可独立scan；query内部直接用公共来源函数。 |
| 独立索引、目标查询回归、事务恢复或提交清单核对 | `hs-knowledge-apply` 的 index-build／index-verify／index-activate、regression／regression-verify、inspect／resume／rollback、prepare-submission／verify-submission；只做所选用途，不要求生产者私人日志或上游通过票据。提交清单核对只读真实 Git，不提交或推送。 |
| 首次准备代码图谱 | 由 Agent 按本 Skill 的“首次初始化 CodeGraph”逐仓执行；CodeGraph MCP 由 harness 提供，图谱查询时核对实际可调用能力。 |
| 首次部署或本机运行依赖缺失 | 按 [部署与执行](references/setup.md) 使用分发仓根的 `deploy.ps1`；本 Skill 不自动安装依赖或部署远端。 |
| 首次配置或修改dbox资料目录 | 实际执行端调用仓内 `python K/knowledge.py source configure`，填写一个绝对目录；无path只核已有配置。固定K下dbox.local.yml仅留本机，模板和ignore上库；配置只核根，不扫描资料，Windows部署不等于远端来源就绪。细节见[部署与执行](references/setup.md#dbox-首次来源配置)。 |
| 找不到项目入口 | 本 Skill 的只读发现 CLI；已有有效项目上下文时直接使用业务能力。 |

## 取得必要上下文并路由

已有部署及有效项目位置、执行端、配置和知识根上下文时直接复用，进入对应已安装能力；不要求每次任务先做环境准备或运行本 Skill 的发现 CLI。配置或执行位置已变化时，重新核对实际入口。

缺少入口信息时，使用本 Skill 的只读发现 CLI；构造请求前读 [公开 API](references/public-api.md)。读取实际项目的 `AGENTS.md` 了解代码仓与开发约定，从根 `config.yml` 的 `knowledge_roots.wifi` 解析知识根 `K`，读取 `K/AGENTS.md` 和 `K/docs-llm-wiki/README.md`，再按任务读取对应操作说明、设计与治理规则。知识库详细边界以实际 K 的入口和文档为准，不依赖根业务 `AGENTS.md` 重复列出知识能力。发现 CLI 要求实际项目 `AGENTS.md` 存在，不自动读取 `AGENTS.md.example` 代替。`code_root` 相对项目根，模块 `path` 相对代码根；以实际配置和文件提供线索，不从芯片／端／特性标签推断宏、构建或运行事实。

按路由读取目标 Skill 或 Workflow 的实际说明并继续执行。人工可以逐个调用节点 Skill；OpenFlow 负责 Workflow 顺序、角色隔离和交棒合法性。节点只校验自身业务输入与固定检查，不要求 Workflow 身份、catalog 登记或上游通过票据。ingest 和治理巡检使用各自已安装的 Workflow；巡检复用相同 P3—P7节点，不嵌套 Workflow。路由本身不表示业务完成。

当前分发8个Skill：source、change-plan、view-materialize、lint、apply、query、explore、maintain（均带 `hs-knowledge-` 前缀）。source保留configure、run、scan、prepare、capture、resolve、resolve-source、record和status各自用途，不把独立调用强绑扫描。公共规则随知识根 `governance/contracts/` 和规则锁提供，不调用兄弟Skill CLI或私有脚本。升级时安装完整8包及配套规则，移除已合并的旧来源包与此前迁出的旧能力；旧操作按原配套版本恢复，历史工具身份和工件不改写。

## 部署或依赖缺项

首次部署或本机依赖缺项时，指向分发仓根的 `deploy.ps1` 和实际知识根的使用说明；命令、安装路径、只读计划与依赖修复选项见 [部署与执行](references/setup.md)。它在 Windows 选择现有 Python，安装能力并直接将知识 ZIP 解压到所选项目位置。日常任务不重复运行部署；本 Skill 不另行引导 Agent 执行 pip 或远端 setup。

部署成功后，按实际项目 `config.yml`、`AGENTS.md` 和 K 入口选择业务能力；存在 `LOCAL_DEPLOYMENT.md` 时读取当地约定。执行端诊断使用 `python K/knowledge.py doctor`，不会自动安装、扫描原件或建库；旧开发setup不随Skill分发。

首次来源准备另在真正执行端完成source.configure；日常不隐式重配。默认全量来源观察包括六类仓内raw与`docs-raw/sources/dbox`逻辑根，未配置或不可达不能当无变化；限定普通raw范围不依赖无关dbox。目录映射和绝对路径仅属本机，来源锁及共享身份保存逻辑地址；已发布依据的恢复不依赖生产者配置。query可能在当次响应及私有Receipt给经核验的absolute当前地址，不能据此写回共享配置或来源锁。

部署脚本不配置宿主 MCP、角色权限或 CodeGraph，也不验证远端 Python。代码仓在远端时，实际任务仍通过宿主已配置且可调用的 SSH MCP 执行，另核对该端 Python、运行依赖和仓内 CLI 路径；本机部署检查不能代替执行端检查。

请求、稿件、记录和索引继续使用实际知识根已有 `.build/`、`logs/`、`artifacts/`。环境、连接或执行能力缺项时报告实际缺口，不将部署完成当作 Workflow 加载、内容复核或业务完成。

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

按目标能力的实际结果报告已完成内容、业务文件引用和未解决缺口。只做发现时报告项目上下文及缺口；业务任务已获授权且条件具备时，继续完成对应任务，不以发现成功或路由成功结束。

产物展示规则见 [writing-guide](references/results/writing-guide.md)，复核见 [review-guide](references/results/review-guide.md)。

新Workflow从正式状态和当前输入开始，使用新operation；不搜索最近draft或旧操作替用户续办。同Workflow明确引用的返工仍可继续，真正未完writer仍受写安全保护。项目上下文和helper环境是派生产物，不进入P7单批清理集合。
