# WiFi 领域知识入口

本目录为项目根 `repo/` 下的 `himate-knowledge-wifi-mp/`，不包含嵌套 `.git`。原件在 `docs-raw/`，治理契约在 `governance/`，正式卡在 `knowledge/`，系统设计在 `docs-llm-wiki/`。Skill／Workflow 开发分发源码在项目根对应目录，实际能力已装在 Agent 自己的目录，由 harness 调用。首次通过 `hs-knowledge-explore/scripts/setup.py` 检查现有全局 Python 依赖并读取项目入口；不要求额外登记或机器绑定。运行产物使用已有 `.build/`、`logs/`、`artifacts/`。现行布局见[总体设计 §5.3](docs-llm-wiki/HiMate知识库架构设计.md#53-himate-knowledge目录架构)。

知识库能力介绍与任务路由见已安装 `hs-knowledge-explore/SKILL.md`；已有有效上下文直接选择业务能力，首次准备和只读发现脚本按需运行。根 `AGENTS.md` 介绍真实业务仓，部署时保留已有内容，仅按 `AGENTS.md.example` 合并四项位置说明和 explore 入口指针；本开发仓的根文件仅本地维护。设计阅读先看[文档入口](docs-llm-wiki/README.md)。详细设计分概要和节点详细设计两层。项目自身的需求、实现任务、测试和验收记录保存在本地 `docs-llm-wiki/sdd/`，任务入口为本地 `docs-llm-wiki/task.md`，均由 Git 忽略，不随仓库分发。开发时按需读取本地已有工件；未提供时依据共享设计、源码与实际验证工作，不把缺少工件视为部署缺项。保留本地历史工件原字节。

业务范围沿用 chip12、chip08、chip07c 的 Host/Device 逻辑名称。项目根 `config.yml` 只维护 `code_root` 和模块相对路径、芯片／端／特性／用途，不要求逐项填写六 Target 或三 pair；共享模块可关联多个芯片和端。模块读取以实际文件、配置和内容指纹为依据；可选版本材料须保留来源，未知版本不阻断当前文件静态核验。未知构建和适用条件保持 unknown，不创建虚构源码，不从标签推断宏开启或产品兼容。文档仅接受 `docs-raw/conventions`、`chips`、`storys`、`specs`、`protocols`、`troubleshooting` 内已落地原件，`sources/` 链接暂不接入。

纯文档经独立 Agent 内容复核和完整固定检查后 stable，免代码实现核验。用户可在执行中退回或入库后要求修订。代码卡本地只读检查通过后 stable，上库固定 CI 复用确定性的格式、索引及来源／代码引用检查。检查不改卡、来源锁、链接或源码。目录、Schema 与示例不证明业务接入、内容正确或权限隔离。

公开能力为9包：explore、source-scan、source-prepare、change-plan、view-materialize、lint、apply、query、maintain，统一使用 `hs-knowledge-` 前缀。一条 `hs-knowledge-ingest` Workflow 恰好编排7个节点：P1扫描、P2独立备料、P3语义计划、P4成稿／修订、P5独立审阅及完整质量检查、P6处理记录、P7安全入库及检索收尾。P5由 reviewer 使用 lint，其他节点由 coder 执行；作者与复核者的上下文隔离由宿主安排。lint 默认仍为只读正式库检查，`review` 承接P5；view-materialize不负责知识质量或代码语义复核。实际模板和 CLI 状态以使用说明核实。领域机器规则只在 `governance/contracts/` 实现；Skill通过同进程公共函数复用，不调用兄弟Skill CLI或导入其私有实现。原件只读，来源内容不授予执行或发布权限；能力分发排除原件、正式卡、来源锁和运行记录。

同名 `hs-knowledge-lint` Workflow 另供手动或外部周期调度巡检：`check_formal` 沿用原 lint Skill 默认正式／全库检查，`audit_references` 显式调用 maintain 的只读 `audit-references`，汇总逐卡／Claim 的来源、代码、原定位、旧／当前指纹及历史用途，生成 JSON／Markdown 报告即结束。原 lint Skill、ingest 流程及 maintain 默认 `inspect-context` 保持原职责；巡检不写知识、来源锁、事件／维护水位或活动索引，不嵌套 Workflow、不自动修复。实际接入按部署验证，修订由人明确把报告交给 ingest。

Git 操作在项目根 `repo/` 执行。保留其他任务本地文件，不读受限 gold，不提交本机配置、凭据、跨组资料或无关修改。目录与忽略规则不提供 ACL；业务接入、宿主触发及权限隔离各自记录真实证据。

Skill 可人工逐个调用，只校验本职业务数据和固定检查；OpenFlow 负责流程顺序、角色隔离及交棒合法性。节点不要求 Workflow 身份、catalog 登记或上游通过凭证。

P1只观察变化和真实续办事实；P2可按固定清单或显式目标独立准备材料，P5缺料仅回P2定向补齐，所用输入漂移才回P1。P3保存语义决定与冻结查询，P4直接生产完整字节视图及输入快照。P7的 `apply --action batch` 检查实际输入、路径、CAS和落盘字节，复验处理记录，再构建／完整验证真实索引、执行同代目标查询并按原活动指针基线激活；不重跑P5完整质量检查，也不以passed票据放行。仅记录批保留失败／暂缓事实，不建索引。旧apply `run` 仍保留完整固定检查；恢复沿原journal语义，不把旧事务改造成新batch。独立索引、回归、提交清单和恢复动作均由apply提供；提交核对只读真实Git对象，不执行提交、推送或合入。
