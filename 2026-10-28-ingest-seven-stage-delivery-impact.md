# ingest 七阶段收敛：能力分发、引用及迁移影响

日期：2026-10-28。状态：SDD 计划，尚未实施。本文件记录当前源码盘点与拟定发布边界；本轮仅提交本次 SDD 文档，没有修改产品实现、执行新版测试或部署运行能力。历史记录保持原字节。路径均以开发仓 `repo/` 为相对基准；`S/`、`F/` 分别表示执行端已有 Skill、Workflow 安装根。

**文档位置：**本次六份 SDD 暂存项目根并纳入 Git；开发完成后按后续指示移入文档忽略目录。入口见[SDD 总览](ingest七阶段重构SDD计划.md)。

## 1. 目标与盘点口径

目标是让 ingest 按 P1—P7 的业务职责组织执行，并将公开知识能力从当前 18 个 Skill 收敛为 8 个。减少公开包、OpenFlow 节点、Agent 交棒与重复上下文读取；保留所需的取证、独立复核、固定检查、恢复、索引和激活机制。包数、节点数和内部模块数是三个不同指标，不能以删除包名代替迁移功能。

本次仅按存在 `SKILL.md` 的目录计 active Skill。当前有 18 个 active Skill、2 个 Workflow、23 份 `artifacts/*.yaml` 产物契约，以及 18 份运行锁和 18 份开发锁。证据是 `skills/common/knowledge/` 的实际文件及 `himate-knowledge-wifi-mp/evals/validate_design.py` 的 `SKILLS`、`ARTIFACT_SCOPE`、`EXTRA_ARTIFACT_SCOPE`。两个历史 confirmation 目录没有现行 `SKILL.md`，不计入 active Skill，也不把它们算成这次要迁移的业务能力。

当前 `himate-knowledge-wifi-mp/tools/deploy/` 与历史 `install_catalog.py` 已不存在。现行准备入口为 `skills/common/knowledge/hs-knowledge-explore/scripts/setup.py`；其 `SKILL.md`、`references/setup.md` 明确不创建 catalog、registry、binding、独立虚拟环境或另一套部署目录。不能把旧部署记录中的安装器、manifest 或绝对路径当作现行分发必需品。现有公开 CLI 仍有可选 `--catalog` 兼容读取，需与必需登记区分。

## 2. 最终公开能力与迁移归属

拟保留的公开 Skill 为：`hs-knowledge-source-scan`、`hs-knowledge-change-plan`、`hs-knowledge-view-materialize`、`hs-knowledge-lint`、`hs-knowledge-apply`、`hs-knowledge-query`、`hs-knowledge-explore`、`hs-knowledge-maintain`。

| 拟删除公开包 | 功能迁往保留包 | 删除前必须保留的行为 |
|---|---|---|
| `hs-knowledge-source-capture` | `source-scan` | raw／代码捕获、提取、确切来源解析、旧版恢复、内容指纹和范围校验 |
| `hs-knowledge-candidate-inspect` | `view-materialize`／`lint`／`apply` 按职责分配 | 稿件类型及生产一致性归 P4；质量规则归 P5；事务停点和写入安全归 P7，不整体搬运旧检查链 |
| `hs-knowledge-candidate-revise` | `view-materialize` | 候选修订、输入与视图失效判定、新操作语义及修订预算 |
| `hs-knowledge-local-check` | `lint` 的 P5 适用代码核验动作 | Agent 逐 Claim 复核指引、真实代码与配置范围、确定性证据绑定校验；执行角色隔离仍由宿主安排 |
| `hs-knowledge-governance-handoff` | `view-materialize` 的确切候选描述 | 描述视图、来源、基线及续办所需业务数据；不制造通过凭证 |
| `hs-knowledge-recover` | `apply` | 按 journal／备份／实际字节恢复或回滚，不重复入库，不覆盖外部编辑 |
| `hs-knowledge-index-build` | `apply` 的 P7 收尾动作 | 构建、完整核验、代次与活动指针基线、shared 快照及显式发布回执兼容 |
| `hs-knowledge-query-regression` | `apply` 的 P7 收尾及独立回归动作，复用公共检索函数 | 冻结查询、确切代次、必需预期、完整结果、CAS 激活及响应丢失复核；不调用 query Skill CLI |
| `hs-knowledge-publish-handoff` | `apply` 的可选提交范围说明／实际提交核对动作 | 仅准备或核对实际 scoped 字节；不自行提交、推送或合入；该动作不属于本地 ingest 完成条件 |
| `hs-knowledge-merge-check` | `lint` 的 P5 显式代码复查兼容动作 | Agent 复核指引与确定性证据绑定校验一并迁移，保留有实际需求的 latest-code recheck；固定 CI 仍使用可信 `K/check.py`，不重新接入 Agent CI |

这些归属是拟定公开边界。`view-materialize` 只负责生产一致性与修订，不负责知识质量或代码语义复核；相关 Agent 复核指引与确定性证据绑定校验统一归 P5 的 `lint`。可以保留多个内部模块与窄函数，不能把十个目录机械拼成一个巨型 CLI。实现阶段先确定请求、动作、输出和错误兼容，再移动代码。收敛完成后，旧十个包不得继续作为必需 sibling CLI、导入来源、默认路由或隐蔽 runner 存在。

`maintain` 必须保留：`workflows/common/knowledge/hs-knowledge-lint/workflow.yaml` 的 `audit_references` 显式调用其只读 `audit-references`，与原 lint 默认 formal／full 检查配套。不能因为它不在 ingest 主线就删除，也不能把巡检的 `register`、`advance` 等写动作接入只读巡检。

CodeGraph 首次初始化已经折入 `hs-knowledge-explore/SKILL.md` 的“首次初始化 CodeGraph”。保留配置中的真实代码仓逐仓检查、初始化及缺项报告；空 `modules` 不建图，`.codegraph/` 不分发。不重新创建 `hs-codegraph-setup`，也不在此次精简中误删 explore 内现有指引。

## 3. 源码引用清理面

### 3.1 不能只删 Workflow 中的 Skill 名

当前跨包调用以安装目录中的 sibling 为先，可选 catalog 仅作兼容位置回退，例如 `hs-knowledge-source-scan/scripts/support.py`、`hs-knowledge-query/scripts/support.py` 的 `Context.call`。删目录前必须把调用端改到新公开动作或适用的内部函数，否则本地源码或旧安装副本可能掩盖缺包。

| 当前调用或引用位置 | 所依赖的拟删除能力 | 迁移要求 |
|---|---|---|
| `source-scan/scripts/prepare.py` | `source-capture` 的捕获、resolve、resolve-source | 同包捕获与解析，保留各材料缺口和恢复边界 |
| `change-plan/scripts/planning.py` | `source-capture` | 所有确切来源恢复改用保留接口，不能恢复为直接随意读路径 |
| `maintain/scripts/maintain.py`、`scripts/audit.py` | `source-capture` | 巡检和日常维护都迁移，保持只读 audit 无副作用 |
| `query/scripts/node.py` | `source-capture`、`index-build` | 查询的 source resolution、generation verify 等依赖迁移；无 catalog、无旧十包仍可 query／receipt／read |
| `query-regression/scripts/node.py` | `index-build` | 整体迁入 P7 后使用同一代次和 expected_active；不得内层重新取基线 |
| `candidate-revise/scripts/revise.py` | `source-capture` | 随修订功能一起迁移，避免残留旧 sibling 调用 |
| `merge-check/scripts/merge.py` | 当前依赖 `local-check`，可选 catalog | 显式复查的 Agent 指引与确定性证据绑定校验一并改用 `lint` 的 P5 动作；不得依赖删除包 |
| 多包 `scripts/support.py` | `hs-knowledge-query-regression` 专用超时分支、包路径和实现身份 | 随新 action 重新定义有限预算及 tool identity，不因改名放宽全部时限 |

其他清理面包括各 Skill 的 `SKILL.md`、`references/`、writing/review guides、产物模板、测试夹具和 helper 中的旧能力名／旧 CLI 文件路径。对历史名称做检索时，只修改当前指令及实现引用；历史 SDD、原始报告、来源内容与真实旧输出不做批量替换。

### 3.2 Workflow、固定检查和文档

- 两条 Workflow 的 `workflow.yaml`、`layouts.yaml`，以及 `entry`、节点 owner、退出条件、恢复／退回出口与 artifact scope 必须一起核对。ingest 节点收敛不改只读巡检的职责。
- `himate-knowledge-wifi-mp/evals/validate_design.py` 的固定 18 Skill 列表、节点映射、owner、完整边、产物 scope、额外契约 ID 随最终图更新；`evals/tests/test_workflows.py` 的合成模板和静态预期同步。不能只让计数等于 8 而漏检残余调用。
- `himate-knowledge-wifi-mp/evals/run_acceptance.py` 按现存 `SKILL.md` 自动发现测试组。删除十包会自然少十组，故必须先把其行为测试迁入新归属包；不能以组数减少宣称验证更快或行为仍覆盖。
- `evals/pipeline_harness.py`、`evals/tests/test_manual_skills.py`、`test_node_pipeline.py`、恢复／clean-clone／来源／索引／查询／超时相关测试中的公开动作和 helper 均需迁移。仅替换名称不足以证明行为等价。
- `governance/specs/sources.md`、`cards.md` 当前仍直接说明 source-capture 公开恢复入口，需改为保留入口。若改动受锁规范／契约／Schema，按实际兼容性更新 `governance/framework.lock.yaml`，不能只换文件而保留错误摘要。
- 共享架构、详细设计、关键点、使用说明、README 与领域入口同步最终 8 包职责、七阶段及实际运行图；`AGENTS.md.example` 保留 explore 指针，不复制详细能力表或引入机器路径。
- 固定 CI 继续复用可信 `K/check.py` 与共享确定性检查，不能因删除 merge-check 包而删除必要检查，也不能用新 Agent 节点替代原固定 CI。

### 3.3 产物契约和环境锁

当前 23 份产物契约来自 18 份 `result.yaml`，加 source-scan 的 prepare／record 两份、change-plan 的 review 一份、publish-handoff 的 submission 一份、maintain 的 audit 一份。保留八包当前占 12 份，待删十包当前占 11 份。这个 12 不是最终契约数量目标：迁入动作仍有不同业务输出和宿主义务，应以新契约设计确定必要产物，不能把删除包对应的必要结果一并丢弃。

OpenFlow 的 artifact ID、from-node scope、出口义务、模板及 guides 属于配套发布单元。旧 ID 如需兼容，限定在明确迁移期间；最终不得出现指向已删除节点／包的契约。当前静态校验对这些字段有精确预期，需与新图一致。

当前 18 包各有运行及开发依赖锁。十包迁出后的依赖必须进入实际新归属包的锁，尤其 source-capture 的 PDF／DOCX／XML 适配依赖与 P7 的加密／发布回执兼容依赖，不能因删包而悄悄缺失。`explore/scripts/setup.py` 读取本包 `requirements.lock.txt` 检查／安装全局依赖，该锁当前承担分发运行依赖集合；新八包锁与此集合须配套，继续支持项目既有 Python 范围。开发依赖锁和运行依赖锁分别维护，不把 pytest 等开发工具塞入运行准备。

## 4. 安装副本、宿主 manifest 和旧操作风险

| 对象 | 风险 | 发布／迁移规则 |
|---|---|---|
| 开发分发源码与执行端 `S/`、`F/` | 本仓删除十包，但执行端旧包仍可被误路由；或先删远端包造成旧 Workflow 断链 | 在各实际执行端安装配套版本并核对可调用入口；最终八包和两 Workflow 作为配套集合验收 |
| OpenFlow 会话绑定的 Workflow／Skill 副本及 manifest | 已运行会话可能继续使用完整旧副本；改全局模板不保证刷新会话副本 | 新会话使用新版本；旧会话先盘点停点，不覆盖运行中副本。保留原模板、其完整 Skill 副本和 manifest 直至该版本操作结束 |
| 历史 catalog 与其中绝对路径 | 旧可选 catalog 可能把新调用回退到旧十包或已移动目录 | 先确认实际部署是否仍传可选 catalog；有则核查版本与路径并退出旧路由。现行架构不新建 catalog，不把机器路径写入共享包 |
| 旧 operation、view、journal、generation、冻结查询 | 数据可能含旧 tool identity、包实现摘要、规则摘要或输出结构；切换实现后原操作可能失效 | 依据实际兼容性决定原版本完成／恢复或显式新操作，不篡改旧身份或原字节“升级” |
| 运行中或待恢复的单写事务 | 新旧 P7 并行或重放可能重复写入、覆盖现场、重新获取错误 CAS 基线 | 对同一知识根只保留一个写者；先检查原 journal、落位文件和 active generation。只续办未完成步骤，不重复 apply |
| 正式知识、来源锁、跨机消费 | 新包直接依赖旧生产机 `.build/`、catalog 或证据缓存，会破坏 clean clone | 继续使用持久原件／正式锁恢复规则；新安装副本缺少生产端临时目录时仍须按既有消费契约工作 |

OpenFlow 本地核对快照的 F115 设计已明确：完整存在的旧会话 Skill 副本不会因项目源更新而自动同步，自动重建处理缺失／不完整副本而非通用升级。这是检查部署副本的依据，不证明公司实际宿主版本已验证。具体旧会话是否可续办需执行端单列验收。

旧 operation 的配套代码／规则／环境身份如需归档，保存在本机既有工件区或既有可恢复版本中，记录必要摘要及确切版本；不把原私有安装根、catalog、旧绝对路径、原件或运行产物塞进共享能力包。归档用于原版本恢复，不作为新版本默认 fallback，更不跨组收集资料。

## 5. expand—migrate—contract 发布顺序

本轮仅规划下列顺序，不执行能力安装或运行发布；SDD 文档按本轮要求正常提交。

### E：先扩展新归属接口

1. 冻结新八包公开动作、七阶段输入输出、独立复核边界、节点／产物契约以及错误和恢复语义；明确每个旧动作的替代入口。
2. 先在保留包内实现迁入功能和内部模块，补齐运行锁／开发锁；此时旧十包暂不物理删除，避免先断调用链。
3. 兼容层只在迁移窗口保留，限定为旧 CLI 到新动作的薄转发，或将旧调用全部改完后再切换；不形成永久第二套实现和另一套 runner。
4. 先搬迁必要的独立预期测试和公开行为覆盖，再更新新 Workflow／契约／文档。验证计划由主 SDD 指定，本记录不报告任何未执行成绩。

### M：迁移调用与部署副本

1. 改完全部保留包、query、maintain、只读巡检、固定 CI 及测试夹具对旧十包的当前引用。
2. 在已授权的实际执行端，检查现有会话和操作停点；备份必要的旧配套能力、Workflow／manifest 与环境身份，不改写业务历史。
3. 先安装能独立工作的完整新八包，再导入配套新 Workflow／产物契约；在新会话验证实际入口和流程。不能只发布 YAML 或只覆盖一个脚本。
4. 旧 operation 若已落位，优先只完成原索引／查询／激活收尾；有未完成写事务则先用配套旧版本恢复。无法证明兼容时保留停点，明确按新操作重走必要步骤，不造 passed 凭证。
5. 对旧运行副本设退出条件：无在跑、无待恢复事务、无只能由旧版解释的必需停点，或已保留可用的独立恢复归档。由实际部署结果决定可否收口。

### C：最后收缩十个公开包

1. 旧调用迁完、必要行为与部署验证完成后，物理删除十个旧包及其独占文档／契约／锁／旧测试入口；已迁入测试和内部实现保留在新归属处。
2. 删除现行路由、Workflow、安装清单或实际部署副本中不再使用的旧入口。若某旧会话仍需旧包，先隔离并完成该会话，不把旧入口混入新默认目录。
3. 再按最终集合盘点：8 个 active Skill、配套 Workflow、实际产物契约数与环境锁数；扫当前引用不应再要求旧十包。历史文件中的真实旧名称不算残余依赖。
4. 发布只包含获授权的当前共享资产；不混入其他受忽略的本地 SDD、机器配置、凭据、历史 catalog、安装根、运行日志、`.build/`、索引或 `.codegraph/`。本次根目录六份 SDD 按明确要求跟踪上库，仅供开发评审，不进入运行能力包。

## 6. 恢复与回退策略

- 安装／加载失败且未产生新写入：恢复配套旧能力集合与旧 Workflow／manifest，保留新版本故障证据，不单独回退某个跨包脚本。
- 新操作已产生候选但未写正式区：保留候选和失败状态，依据原输入／规则／基线选择继续或新操作；不把旧复核记录改绑到新视图。
- 新 P7 已落位或 active 已变化：先核 journal、正式文件、候选代、冻结查询和原 expected_active，只补齐缺失收尾。不能把重新执行整个 P7 当回滚，不能强行将 active 指针改回旧值。
- 需要撤销已落位内容：走既有恢复适用条件或明确的新修订操作，保留实际历史；不通过删除正式卡、原件、记录或旧索引来伪装未发生。
- 合约／规则不兼容：使用归档的配套版本处理其原操作；若新版本不能解释旧停点，显式阻断并报告，不借旧 catalog 绕过现行范围、规则或来源检查。

恢复成功、静态校验、隔离合成流程、实际 OpenFlow／SSH 接入及性能改善分别记录。删除十包完成不等于公司 API 提速或独立角色隔离已验收；后者需要真实运行的节点、模型调用、工具、SSH 与脚本分段耗时及宿主证据。
