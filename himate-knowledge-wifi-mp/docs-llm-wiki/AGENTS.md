# HiMate 设计与开发文档入口

本目录平铺保留架构设计、详细设计、知识库关键点、使用说明与入口文档。项目自身的 `sdd/` 和 `task.md` 是 Git 忽略的本地开发工件，不随仓库分发。先按任务选择入口，避免全量加载。

| 任务 | 阅读入口 |
|---|---|
| 目录职责、系统分层和三条链路 | [HiMate知识库架构设计.md](HiMate知识库架构设计.md) |
| 流程节点、判断逻辑及节点内文件分工 | [知识库详细设计.md](知识库详细设计.md)，先概要、后详细 |
| WiFi-MP 向其他领域迁移、目录扩展与配套能力边界 | [知识库关键点.md](知识库关键点.md) |
| 文档导航与部署约定 | [README.md](README.md) |
| 运行依赖准备、部署后的日常命令与排错 | [使用说明.md](使用说明.md) |
| 需求、实现任务与实际验证记录 | 本地已有的 `task.md`、`sdd/`；无本地工件时以共享设计、源码与实际验证为准 |

现行名称和目录以架构设计 §5.3 为准，用户后续明确决定优先。唯一领域根为 `himate-knowledge-wifi-mp/`；项目根 `skills/common/knowledge/`、`workflows/common/knowledge/` 仅表示开发分发源码。实际能力在 Agent 自己的目录，首次使用其 `hs-knowledge-explore/scripts/setup.py` 检查现有全局依赖并读取项目配置，日常由 harness 调用。节点不要求 catalog 或流程登记，业务运行不依赖项目根能力源码。项目根统一以 `repo/` 示意，Git 在项目根执行；知识根和能力目录不建立嵌套 `.git`，业务代码保留项目实际多目录结构。

目录图采用默认布局，实际知识根按根 `config.yml` 的 `knowledge_roots.wifi` 解析，允许安全嵌套；项目配置由用户在这份文件维护。根 `AGENTS.md` 由业务仓维护代码架构与开发约定，本开发仓仅本地保存；分发 `AGENTS.md.example` 供合并四项位置说明和 explore 入口指针，不覆盖业务仓已有文件。全库能力介绍和路由归 `hs-knowledge-explore`；首次准备与后续只读发现按需执行，已有上下文直接调用业务能力。SSH 信息放该 Skill 的 `config.env`，harness 负责连接并核对执行端实际可调用的能力；入口提示不代表已上传脚本或已验证远端，不将调用端路径当成远端路径。缺执行能力时先报告并讨论方案，不自建 runner 或工具副本。产物沿用 K 的 `.build/`、`logs/`、`artifacts/`，操作集中见[使用说明](使用说明.md)。

项目配置以 `code_root` 和 `modules` 的相对路径、芯片、端、特性及用途说明架构；不要求手填绝对代码根、六 Target／三 pair 或重复授权。新配置按模块范围读取实际文件并固定内容指纹；版本仅采用有出处的材料，未知不阻断当前文件静态核验。目录标签不替代宏、构建或协议事实。使用说明讲填法和调用，详细设计第 5 章讲节点文件设计，知识库关键点说明跨领域适配，并集中维护路径与核验边界；历史配置与验证记录按原版本解释。

架构设计解释分层与协作；详细设计分概要和节点设计两层，以流程图、分支条件和文件职责表达。设计正文不记开发轮次、票据状态、Agent 工作进度或历史测试成绩；这些进入 SDD 工件。系统设计不构成正式领域事实，Schema/Contract 机器规则归 `../governance/`，此处不另建执行契约。

统一约定：公开能力为9个Skill，ingest恰好7个节点。P1 source-scan只观察变化及续办；P2 source-prepare按固定单元或显式目标备料，不要求先有P1记录，补料不默认全扫；P3 change-plan保存语义计划和冻结查询；P4 view-materialize直接成稿、修订、描述及固定实际输入；P5 lint由独立reviewer阅读计划、稿件、新旧证据并执行一次完整质量检查，材料／语义／字节问题分别回P2／P3／P4；P6 source-scan.record对账处理记录；P7 apply.batch安全落位、完整验证真实索引、执行同代目标查询并CAS激活。其他节点由coder执行；无变化且无义务则结束，不制造记录。保持详设L1—L5编号与独立lint默认formal/full，CI只复用固定规则，不调用Agent。

P4只负责生产一致性，不做知识质量或代码语义复核。P5同时承接文档、代码、归卡与实质skip的独立审阅，固定脚本只校验确定性证据、逐Claim理由及确切内容绑定；它们不认证作者身份或代替内容判断。角色、上下文隔离与执行顺序由宿主／人工测试者落实，Skill不要求Workflow身份、catalog或上游通过票据。未知Target、版本、构建条件保持unknown；静态源码结论不统一要求编译产物，编译／运行／实测断言须有实际材料。

Skill内部通过受锁公共函数复用领域规则，不委派兄弟CLI或导入兄弟私有脚本。P7.batch重核真实输入快照、写删集合、旧基线、落盘字节及记录绑定，不重跑P5完整质量检查；写后重新捕获索引基线。旧apply.run仍执行原完整固定检查，恢复遵守原journal模式。独立index-build/index-verify/index-activate、regression/regression-verify、prepare-submission/verify-submission及inspect/resume/rollback均在apply，query共享同一查询算法。回归沿冻结用例、确切代次和原expected_active，不因重试重设CAS。仅记录批不夹带失败稿件或索引。

用户可随时退回或入库后新建修订，输入变化须重新取得实际材料。Git提交、固定CI与合入仍是人工后续，提交清单核对只读真实HEAD、commit、blob、删除和变更范围；本地完成不表示CI、上库或语义全面通过。共享索引的knowledge_commit仅核仓库快照，显式签名回执另核发布身份。保留历史工件原字节和旧操作事实；原件未变的明确修卡仍进入P2。

lint 的新增编排限定为只读巡检：`F/hs-knowledge-lint/` 只有 `check_formal`、`audit_references` 两个 `type: skill` 节点，前者沿用 `S/hs-knowledge-lint/` 默认 formal／full，后者显式调用 maintain 的只读 `audit-references`，汇总 JSON／Markdown 报告后结束。保留L1—L5检查编号、lint默认formal/full与maintain默认 `inspect-context`；不自动修复，不嵌套 Workflow，不新增 runner。外部系统负责周期触发；巡检不写正式知识、来源锁、事件／水位或活动索引。描述新能力时区分设计、实现验证和真实宿主接入，报告完成不表示问题已修复；需要修订由人明确交 ingest。

实现修改前核对共享设计、源码与现有测试；本地有对应 SDD 需求、设计、任务和测试计划时一并参考，依据实际验证更新本地记录。保留历史工件原字节，不批量替换旧记录路径或状态，不把本地开发工件重新加入 Git。普通文档整理不读受限 gold。文档独立内容复核、本地代码只读核验与固定 CI、六类原件及未知业务上下文遵循上级 AGENTS。

不新增 research、experiments、agents、superpowers 或设计文档子目录。系统设计优先维护架构与详细设计两份主文档，路径与部署约定集中维护在知识库关键点；操作写使用说明，任务、测试、发布与历史记录写相应 SDD 工件。
