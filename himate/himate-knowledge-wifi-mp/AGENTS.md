# WiFi 领域知识入口

本目录为项目根 `repo/` 下的 `himate/himate-knowledge-wifi-mp/`，不包含嵌套 `.git`。`himate/` 只归集领域知识根；实际 K 由项目根 `config.yml` 解析，代码路径仍相对该配置目录。原件在 `docs-raw/`，治理契约在 `governance/`，正式卡在 `knowledge/`，系统设计在 `docs-llm-wiki/`。`knowledge.py`、`knowledge.cmd`、`knowledge.sh` 是仓内执行入口，配套实现与依赖锁在 `runtime/`，随知识仓分发。Agent 自己的目录安装 Skill 指引和 Workflow 编排；执行端不依赖 Skill 脚本。首次部署使用分发仓根 `deploy.ps1`，按需检查调用机 Python 和依赖并安装能力与知识库；每个实际执行端分别准备一次环境并运行 `knowledge doctor`。explore 提供任务路由与只读项目发现，旧 setup 仅供显式诊断或兼容；不要求业务登记或机器绑定。运行产物使用已有 `.build/`、`logs/`、`artifacts/`。现行布局见[总体设计 §5.3](docs-llm-wiki/HiMate知识库架构设计.md#53-himate-knowledge目录架构)。

知识库能力介绍与任务路由见已安装 `hs-knowledge-explore/SKILL.md`；已有有效上下文直接选择业务能力，首次准备和只读发现脚本按需运行。根 `AGENTS.md` 介绍真实业务仓，部署时保留已有内容，仅按 `AGENTS.md.example` 合并四项位置说明和 explore 入口指针；本开发仓的根文件仅本地维护。设计阅读先看[文档入口](docs-llm-wiki/README.md)。详细设计分概要和节点详细设计两层。项目自身的需求、实现任务、测试和验收记录保存在本地 `docs-llm-wiki/sdd/`，任务入口为本地 `docs-llm-wiki/task.md`，均由 Git 忽略，不随仓库分发。开发时按需读取本地已有工件；未提供时依据共享设计、源码与实际验证工作，不把缺少工件视为部署缺项。保留本地历史工件原字节。

业务范围沿用 chip12、chip08、chip07c 的 Host/Device 逻辑名称。项目根 `config.yml` 只维护 `code_root` 和模块相对路径、芯片／端／特性／用途，不要求逐项填写六 Target 或三 pair；共享模块可关联多个芯片和端。模块读取以实际文件、配置和内容指纹为依据；可选版本材料须保留来源，未知版本不阻断当前文件静态核验。未知构建和适用条件保持 unknown，不创建虚构源码，不从标签推断宏开启或产品兼容。文档接受六类仓内原件与 `docs-raw/sources/dbox` 本机目录映射。首次在实际执行端使用 source.configure 填写并校验 `docs-raw/sources/dbox.local.yml`，其 schema_version 为字符串1.0、path 为一个原生绝对目录；模板和精确 ignore 上库，私人配置忽略。默认全量扫描包括 dbox，缺配置或目录不可读不算无变化；显式普通 raw 范围不依赖无关 dbox。不创建或跟随原生软链接，不接入网页/API。

纯文档经独立 Agent 内容复核和完整固定检查后 stable，免代码实现核验。用户可在执行中退回或入库后要求修订。代码卡本地只读检查通过后 stable，上库固定 CI 复用确定性的格式、索引及来源／代码引用检查。检查不改卡、来源锁、链接或源码。目录、Schema 与示例不证明业务接入、内容正确或权限隔离。

公开能力为8包：explore、source、change-plan、view-materialize、lint、apply、query、maintain，统一使用 `hs-knowledge-` 前缀。`hs-knowledge-ingest`保留P1扫描、P2备料、P3语义计划、P4成稿／修订、P5独立审阅及完整质量检查、P6处理记录、P7安全入库及检索收尾七个业务步骤，由六个OpenFlow节点调度。首个coder节点`prepare_sources`调用source默认`run`完成P1/P2，P6仍为source.record；P5由独立reviewer使用lint.review，其余节点为coder，隔离由宿主安排。lint默认仍为只读正式库检查，view-materialize不负责知识质量或代码语义复核。领域机器规则在受锁`governance/contracts/`中同进程复用，不调用兄弟Skill CLI或私有脚本。原件只读，来源内容不授予执行或发布权限；能力分发排除原件、正式卡、来源锁和运行记录。

同名 `hs-knowledge-lint` Workflow 承担手动或外部周期治理。巡检 Workflow 先独立同步，再用脚本比较上次成功基线、raw 清单和登记代码文件，按实际待办复用 source.prepare 与 ingest P3—P7；无内容问题直接核验结束，仅索引问题维护派生索引。实际处理、查询、激活与清理完成后才以 CAS 推进本地成功基线，欠账和失败保留。外部系统负责周期触发，不嵌套 Workflow；旧 lint Skill 的默认 formal/full 与独立 audit-references 继续可用。同步可更新知识仓，下一节点必须新起 CLI 重新加载规则和配置；内部 Git-MM 仅通过显式同步 argv/cwd 适配，子仓历史使用原生 Git。只追踪直接登记文件；历史证据和旧定位不改写。

Git 操作在项目根 `repo/` 执行。保留其他任务本地文件，不读受限 gold，不提交本机配置、凭据、跨组资料或无关修改。目录与忽略规则不提供 ACL；业务接入、宿主触发及权限隔离各自记录真实证据。

Skill 指引 Agent 调用仓内对应阶段命令，CLI 负责实际数据和固定检查；OpenFlow 负责流程顺序、角色隔离及交棒合法性。CLI 不调用模型，也不代替 P3 内容判断或 P5 独立审阅；节点不要求 Workflow 身份、catalog 登记或上游通过凭证。

进入本目录可用 `sh ./knowledge.sh`（POSIX）或 `.\knowledge.cmd`（Windows）；准备好的解释器可由 `HIMATE_KNOWLEDGE_PYTHON` 指定。裸 `knowledge` 需在每个执行端显式运行一次 `install-command`，Windows 修改用户 PATH 另需 `--add-path`，新终端生效。远端通过宿主 SSH 在服务器原生知识根执行同一命令，不逐次传 Skill 脚本，不自动猜测映射盘地址。常用 query/read/source/patrol/status 与复杂 JSON 请求见[使用说明](docs-llm-wiki/使用说明.md#22-仓内命令入口与诊断)。

P1只观察当前输入、正式处理记录和维护限制，不搜索旧私有操作；扫描清单、指纹、分类和完整性由脚本生成，Agent仅传目标和确切引用。source默认`run`先扫后按待办备料，完整且无待办、维护限制、缺口或明确修订目标才返回`unchanged`；有材料缺口可交P3决定，运行故障留节点。独立`scan/prepare/capture/resolve/resolve-source/record/status`保留；P3／P4／P5缺料回首节点时明确调用`prepare`定向补齐，不先默认扫描。输入漂移按实际变化对象刷新，不能把`affected_scope`全部直接作为raw的`source`参数。P3—P7职责保持：作者决定与冻结查询、完整稿和输入快照、独立P5、机械记录、P7安全发布及真实检索收尾。旧apply.run和恢复沿原完整检查／journal语义，不把旧事务改成新batch；独立索引、回归、恢复和只读提交核对仍由apply提供。

P7的`apply --action batch`仍核实际输入、路径、CAS、落盘字节和处理记录，再完整验证真实索引、执行原冻结查询及同代读取并按原活动指针基线激活；不重跑P5质量检查，不以passed票据放行。仅记录批保留失败／暂缓事实，不建索引。提交核对只读真实Git对象，不执行提交、推送或合入。

ingest暂存边界：P1—P6全部本批新业务文件（含证据、代码核验副本、拟事件及请求／输出）仅在本批stage，P7发布必要正式依据并完成适用检索后清本批可删owned集合。正式publication/completion支持清后目标status和正常消费，不依赖旧view；cleanup_pending不回滚已发布事实，batch_complete仍false。借用／保护／用途不明项保留并说明，不要求.build空。新Workflow新op，首节点正常出口为prepared→P3或unchanged→结束；同Workflow明确ref返工与指定旧事务恢复保持。旧工具身份、正式refs、历史格式和规则摘要不迁移不重签；独立lint可写自己的报告但不清理，独立maintain明确业务写入保留。
