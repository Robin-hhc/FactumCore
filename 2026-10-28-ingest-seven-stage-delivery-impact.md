# ingest 七阶段收敛：能力分发、引用及迁移影响

日期：2026-10-28。状态：源码迁移与十包删除已落实，源码机制验收已完成。盘点的“当前18包”等数据均指改前基线 `ae02196`；最终交付清单及实际验收另列。历史记录保持原字节。路径以开发仓 `repo/` 为相对基准；`S/`、`F/` 表示实际执行端 Skill、Workflow 安装根。

**文档位置：**本次六份 SDD 继续保留项目根并纳入 Git；本次收尾不搬动或改为忽略。入口见[SDD 总览](ingest七阶段重构SDD计划.md)。

## 1. 目标与盘点口径

本轮已让 ingest 按 P1—P7 的业务职责组织执行，并将公开知识能力从改前 18 个 Skill 调整为最终 9 个：保留原方案的8包，新增P2独立备料包 `hs-knowledge-source-prepare`，原18包中的10个旧包已在功能迁移及替代验证后删除，涉及 143 个 Git 纳管文件。P1／P2拆分已落实。减少公开包、OpenFlow 节点、Agent 交棒与重复上下文读取；保留所需的取证、独立复核、固定检查、恢复、索引和激活机制。包数、节点数和内部模块数是三个不同指标，不能以删除包名代替迁移功能。

以下盘点仅按改前存在 `SKILL.md` 的目录计 active Skill。改前有 18 个 active Skill、2 个 Workflow、23 份 `artifacts/*.yaml` 产物契约，以及 18 份运行锁和 18 份开发锁。证据是改前 `skills/common/knowledge/` 的实际文件及 `himate-knowledge-wifi-mp/evals/validate_design.py` 的清单。两个历史 confirmation 目录没有现行 `SKILL.md`，不计入 active Skill，也不把它们算成这次要迁移的业务能力。最终交付为九包、七个 ingest 节点、两个只读 lint 节点及 22 个公共模块。

当前 `himate-knowledge-wifi-mp/tools/deploy/` 与历史 `install_catalog.py` 已不存在。现行准备入口为 `skills/common/knowledge/hs-knowledge-explore/scripts/setup.py`；其 `SKILL.md`、`references/setup.md` 明确不创建 catalog、registry、binding、独立虚拟环境或另一套部署目录。不能把旧部署记录中的安装器、manifest 或绝对路径当作现行分发必需品。现有公开 CLI 仍有可选 `--catalog` 兼容读取，需与必需登记区分。

## 2. 最终公开能力与迁移归属

最终公开 Skill 为：`hs-knowledge-source-scan`、`hs-knowledge-source-prepare`（新增）、`hs-knowledge-change-plan`、`hs-knowledge-view-materialize`、`hs-knowledge-lint`、`hs-knowledge-apply`、`hs-knowledge-query`、`hs-knowledge-explore`、`hs-knowledge-maintain`。主线使用前六包，query／explore／maintain为另三包。

P1由source-scan扫描变化、待办及实际续办位置；P2由新source-prepare直接承接原prepare和source-capture的实际能力，不委派旧CLI。P2可消费实际扫描清单，也可按明确目标独立备料，不以上游通过状态为条件；公共来源函数由多个调用者直接复用。P5补材料只返回P2，不默认重扫P1；本次采用的来源／配置／规则等输入漂移时才按新扫描／新操作规则处理。P6保留source-scan.record，T00已确认该入口与来源处理账本衔接。

| 已删除公开包 | 功能迁往保留包 | 迁移时保留的行为 |
|---|---|---|
| `hs-knowledge-source-capture` | 新 `source-prepare`，并提取公共来源函数 | 与原prepare一起直接提供raw／代码捕获、提取、新旧材料及旧卡整理、确切来源解析、旧版恢复、内容指纹和范围校验；不转调旧CLI |
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

下表追溯改前跨包调用：其以安装目录中的 sibling 为先，可选 catalog 仅作兼容位置回退，例如原 `hs-knowledge-source-scan/scripts/support.py`、`hs-knowledge-query/scripts/support.py` 的 `Context.call`。本轮已将调用端迁至公开动作或适用的公共函数，并以无旧十包的隔离分发验证；实际宿主副本仍需单列升级。

| 改前调用或引用位置 | 原依赖能力 | 已实施的迁移约束 |
|---|---|---|
| `source-scan/scripts/prepare.py` | `source-capture` 的捕获、resolve、resolve-source | 原prepare连同实际捕获／解析迁入新source-prepare，保留材料缺口和恢复边界；source-scan只保留P1扫描及已定P6.record |
| `change-plan/scripts/planning.py` | `source-capture` | 确切来源恢复直接复用公共函数，不调用新source-prepare或旧source-capture CLI，也不能恢复为随意读路径 |
| `maintain/scripts/maintain.py`、`scripts/audit.py` | `source-capture` | 巡检和日常维护直接复用公共来源函数，保持只读audit无副作用，不委派P2 CLI |
| `query/scripts/node.py` | `source-capture`、`index-build` | source resolution、generation verify等直接复用公共函数，不依赖P2或其他兄弟CLI；无catalog、无旧十包仍可query／receipt／read |
| `query-regression/scripts/node.py` | `index-build` | 整体迁入 P7 后使用同一代次和 expected_active；不得内层重新取基线 |
| `candidate-revise/scripts/revise.py` | `source-capture` | 随修订功能一起迁移，避免残留旧 sibling 调用 |
| `merge-check/scripts/merge.py` | 当前依赖 `local-check`，可选 catalog | 显式复查的 Agent 指引与确定性证据绑定校验一并改用 `lint` 的 P5 动作；不得依赖删除包 |
| 多包 `scripts/support.py` | `hs-knowledge-query-regression` 专用超时分支、包路径和实现身份 | 随新 action 重新定义有限预算及 tool identity，不因改名放宽全部时限 |

其他清理面包括各 Skill 的 `SKILL.md`、`references/`、writing/review guides、产物模板、测试夹具和 helper 中的旧能力名／旧 CLI 文件路径。原source-scan.prepare现行接口、模板和测试调用要迁往新包，不继续被新P2委派；P6.record保留，T00已确认机械转写边界。对历史名称做检索时，只修改当前指令及实现引用；历史 SDD、原始报告、来源内容与真实旧输出不做批量替换。

### 3.2 Workflow、固定检查和文档

- 两条 Workflow 的 `workflow.yaml`、`layouts.yaml`，以及 `entry`、节点 owner、退出条件、恢复／退回出口与 artifact scope 必须一起核对。ingest 节点收敛不改只读巡检的职责。
- `himate-knowledge-wifi-mp/evals/validate_design.py` 的固定18 Skill列表、节点映射、owner、完整边、产物scope、额外契约ID随最终9包和七节点图更新；P1绑定source-scan，P2绑定新source-prepare，P6保留source-scan.record。`evals/tests/test_workflows.py` 的合成模板和静态预期同步，不能只让计数等于9而漏检残余调用。
- `himate-knowledge-wifi-mp/evals/run_acceptance.py` 按现存 `SKILL.md` 自动发现测试组。新增source-prepare会多一组、删除十包会少十组，故必须先把原prepare及source-capture等行为测试迁入实际新归属包；不能以组数减少宣称验证更快或行为仍覆盖。
- `evals/pipeline_harness.py`、`evals/tests/test_manual_skills.py`、`test_node_pipeline.py`、恢复／clean-clone／来源／索引／查询／超时相关测试中的公开动作和 helper 均需迁移。仅替换名称不足以证明行为等价。
- `governance/specs/sources.md`、`cards.md` 当前仍直接说明 source-capture 公开恢复入口，需改为保留入口。若改动受锁规范／契约／Schema，按实际兼容性更新 `governance/framework.lock.yaml`，不能只换文件而保留错误摘要。
- 共享架构、详细设计、关键点、使用说明、README与领域入口同步最终9包、主线六包加三个独立用途、七阶段及实际运行图；explore路由区分P1扫描、P2明确目标独立备料和P5定向补料。`AGENTS.md.example` 保留explore指针，不复制详细能力表或引入机器路径。
- 固定 CI 继续复用可信 `K/check.py` 与共享确定性检查，不能因删除 merge-check 包而删除必要检查，也不能用新 Agent 节点替代原固定 CI。

### 3.3 产物契约和环境锁

本小节保留改前分发盘点及迁移约束，不描述最终文件数量。改前23份产物契约来自18份 `result.yaml`，加source-scan的prepare／record两份、change-plan的review一份、publish-handoff的submission一份、maintain的audit一份。八个继续保留的旧包改前占12份，删除十包改前占11份；新增source-prepare当时尚没有文件。12不是最终契约数量目标：原prepare的材料产物已迁往P2，新包承接捕获／解析的必要输出、模板及错误契约；source-scan保留扫描和record产物，必要结果未随旧包删除。

OpenFlow 的 artifact ID、from-node scope、出口义务、模板及 guides 属于配套发布单元。旧 ID 如需兼容，限定在明确迁移期间；最终不得出现指向已删除节点／包的契约。当前静态校验对这些字段有精确预期，需与新图一致。

改前18包各有运行及开发依赖锁，共36份，这是改前盘点。十包迁出后的依赖已进入实际新归属包的锁，尤其source-capture的PDF／DOCX／XML适配依赖迁入新source-prepare，P7的加密／发布回执兼容依赖随实际归属迁入。新包具备运行锁、开发锁、SKILL、独立CLI/API说明、artifact／模板和测试；原prepare与source-capture的业务预期迁入新入口，覆盖独立明确目标、扫描清单、补料及输入漂移。

`explore/scripts/setup.py` 读取本包 `requirements.lock.txt` 检查／安装全局依赖，该锁当前承担分发运行依赖集合；目标9包的运行锁与此集合须配套，继续支持项目既有Python范围。新包复用现有explore.setup，不新增独立准备体系、runner或catalog。开发依赖锁和运行依赖锁分别维护，不把pytest等开发工具塞入运行准备。

## 4. 安装副本、宿主 manifest 和旧操作风险

| 对象 | 风险 | 发布／迁移规则 |
|---|---|---|
| 开发分发源码与执行端 `S/`、`F/` | 新P2未安装、原prepare仍被路由，或执行端旧十包继续掩盖依赖；先删远端包还会造成旧Workflow断链 | 在各实际执行端安装配套版本并核对新source-prepare独立入口；最终9包和两Workflow作为配套集合验收 |
| OpenFlow 会话绑定的 Workflow／Skill 副本及 manifest | 已运行会话可能继续使用完整旧副本；改全局模板不保证刷新会话副本 | 新会话使用新版本；旧会话先盘点停点，不覆盖运行中副本。保留原模板、其完整 Skill 副本和 manifest 直至该版本操作结束 |
| 历史 catalog 与其中绝对路径 | 旧可选 catalog 可能把新调用回退到旧十包或已移动目录 | 先确认实际部署是否仍传可选 catalog；有则核查版本与路径并退出旧路由。现行架构不新建 catalog，不把机器路径写入共享包 |
| 旧 operation、view、journal、generation、冻结查询 | 数据可能含旧 tool identity、包实现摘要、规则摘要或输出结构；切换实现后原操作可能失效 | 依据实际兼容性决定原版本完成／恢复或显式新操作，不篡改旧身份或原字节“升级” |
| 运行中或待恢复的单写事务 | 新旧 P7 并行或重放可能重复写入、覆盖现场、重新获取错误 CAS 基线 | 对同一知识根只保留一个写者；先检查原 journal、落位文件和 active generation。只续办未完成步骤，不重复 apply |
| 正式知识、来源锁、跨机消费 | 新包直接依赖旧生产机 `.build/`、catalog 或证据缓存，会破坏 clean clone | 继续使用持久原件／正式锁恢复规则；新安装副本缺少生产端临时目录时仍须按既有消费契约工作 |

OpenFlow 本地核对快照的 F115 设计已明确：完整存在的旧会话 Skill 副本不会因项目源更新而自动同步，自动重建处理缺失／不完整副本而非通用升级。这是检查部署副本的依据，不证明公司实际宿主版本已验证。具体旧会话是否可续办需执行端单列验收。

旧 operation 的配套代码／规则／环境身份如需归档，保存在本机既有工件区或既有可恢复版本中，记录必要摘要及确切版本；不把原私有安装根、catalog、旧绝对路径、原件或运行产物塞进共享能力包。归档用于原版本恢复，不作为新版本默认 fallback，更不跨组收集资料。

## 5. expand—migrate—contract 发布顺序

本轮按以下顺序实施；源码发布、实际安装与宿主验证分别记录。

### E：先扩展新归属接口

1. 冻结最终9包公开动作、七阶段输入输出、P1／P2边界、独立复核、节点／产物契约以及错误和恢复语义；明确每个旧动作的替代入口。P6保留source-scan.record，T00已确认机械转写与处理账本边界。
2. 先创建source-prepare并直接迁入原prepare和source-capture的实际能力，在其他保留包内实现相应迁入功能及公共函数，补齐包、API、artifact、测试和运行／开发锁。此时旧十包暂不物理删除，避免先断调用链。
3. 兼容层只在迁移窗口保留，限定为旧 CLI 到新动作的薄转发，或将旧调用全部改完后再切换；不形成永久第二套实现和另一套 runner。
4. 先搬迁必要的独立预期测试和公开行为覆盖，再更新新 Workflow／契约／文档。验证计划由主 SDD 指定，本记录不报告任何未执行成绩。

### M：迁移调用与部署副本

1. 改完全部保留包、query、maintain、只读巡检、固定 CI 及测试夹具对旧十包的当前引用。
2. 在已授权的实际执行端，检查现有会话和操作停点；备份必要的旧配套能力、Workflow／manifest 与环境身份，不改写业务历史。
3. 先安装能独立工作的完整9包，再导入配套新Workflow／产物契约；在新会话验证P2明确目标独立备料、P1清单备料、P5只回P2补料及所用输入漂移处理。不能只发布YAML、只覆盖脚本或用P1通过票据代替P2实际输入。
4. 旧 operation 若已落位，优先只完成原索引／查询／激活收尾；有未完成写事务则先用配套旧版本恢复。无法证明兼容时保留停点，明确按新操作重走必要步骤，不造 passed 凭证。
5. 对旧运行副本设退出条件：无在跑、无待恢复事务、无只能由旧版解释的必需停点，或已保留可用的独立恢复归档。由实际部署结果决定可否收口。

### C：最后收缩十个公开包

1. T14在删除源码目录前，先排除旧十包做隔离9包干净安装和旧18包升级验证，包含新P2、原prepare及捕获／恢复的替代用途。旧调用迁完且这些删前验证完成后，物理删除原18中的十个旧包及其独占文档／契约／锁／旧测试入口；已迁入测试和内部实现保留在新归属处。
2. 删除现行路由、Workflow、安装清单或实际部署副本中不再使用的旧入口。若某旧会话仍需旧包，先隔离并完成该会话，不把旧入口混入新默认目录。
3. T15在T14删除后再次按最终交付产物复验：9个active Skill、配套Workflow、实际产物契约与环境锁、安装／发现、完整公开用途、干净clone及旧安装升级；不能以删前隔离验证代替删后复验。扫当前引用不应再要求旧十包或新P2转调原prepare；历史文件中的真实旧名称不算残余依赖。
4. 发布只包含获授权的当前共享资产；不混入其他受忽略的本地 SDD、机器配置、凭据、历史 catalog、安装根、运行日志、`.build/`、索引或 `.codegraph/`。本次根目录六份 SDD 按明确要求跟踪上库，仅供开发评审，不进入运行能力包。

## 6. 恢复与回退策略

- 安装／加载失败且未产生新写入：恢复配套旧能力集合与旧 Workflow／manifest，保留新版本故障证据，不单独回退某个跨包脚本。
- 新操作已产生候选但未写正式区：保留候选和失败状态，依据原输入／规则／基线选择继续或新操作；不把旧复核记录改绑到新视图。
- 新 P7 已落位或 active 已变化：先核 journal、正式文件、候选代、冻结查询和原 expected_active，只补齐缺失收尾。不能把重新执行整个 P7 当回滚，不能强行将 active 指针改回旧值。
- 需要撤销已落位内容：走既有恢复适用条件或明确的新修订操作，保留实际历史；不通过删除正式卡、原件、记录或旧索引来伪装未发生。
- 合约／规则不兼容：使用归档的配套版本处理其原操作；若新版本不能解释旧停点，显式阻断并报告，不借旧 catalog 绕过现行范围、规则或来源检查。

恢复成功、静态校验、隔离合成流程、实际 OpenFlow／SSH 接入及性能改善分别记录。删除十包完成不等于公司 API 提速或独立角色隔离已验收；后者需要真实运行的节点、模型调用、工具、SSH 与脚本分段耗时及宿主证据。

## 7. 当前交付状态

T00—T14 已实现。T15 的九包隔离分发及机制已验证，实际宿主旧会话、安装副本和配套 Workflow 的升级未操作；第 4、5 节的部署副本规则继续作为执行清单。T16 已通过 SSH 在服务器实测合成脚本链，OpenFlow、公司 API、模型等待和真实 reviewer 上下文未测。

规则版本及最终 SHA-256 统一见[验证记录](2026-10-28-ingest-seven-stage-validation-plan.md#7-本次执行记录)。`b9` 完整验收及末次修复针对回归已完成，最终服务器性能见验证记录。本次八份根目录文档继续跟踪，不搬动，也不进入运行能力包。
