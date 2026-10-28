# ingest 七阶段 Skill 收敛与能力迁移计划

2026-10-28。状态：设计草案，待与需求和接口设计一起锁定；不是现行执行规范。本轮只编写并提交设计规划，不删除包，不修改实现、Workflow、规则、正式知识或历史产物，不执行新版验证或部署。

**文档位置：**本次六份 SDD 暂存项目根并纳入 Git；开发完成后按后续指示移入文档忽略目录。入口见[SDD 总览](ingest七阶段重构SDD计划.md)。

本计划承接[七阶段设计对齐稿](2026-10-28-ingest-seven-stage-design-proposal.md)。目标是从现有 18 个公开 Skill 收敛到 8 个：正常 ingest 使用 5 个主 Skill 完成 P1—P7，另保留查询、项目入口和维护能力。删除的是重复的公开包装和执行链，不能同时删除仍然需要的业务功能。

以下 `K` 表示实际知识根，`repo/` 表示项目根。路径均以相应根为基准，不绑定机器目录。表中的新动作名均为**设计建议，尚未实现，须在接口设计阶段锁定**。

## 1. 最终公开能力集合

| 保留的公开 Skill | 最终职责 | 主线位置／独立用途 |
|---|---|---|
| 扫描与备料 `hs-knowledge-source-scan` | raw 清单差分、实际原件／代码捕获和确切来源解析、材料准备、处理记录转写及状态观察 | P1、P2、P6；独立捕获／解析／查看进度 |
| 内容决策 `hs-knowledge-change-plan` | 作者的逐单元处置、逐 Claim 判断、归卡计划和冻结查询预期 | P3；独立保存明确作者计划 |
| 完整稿件生产 `hs-knowledge-view-materialize` | 一次组织候选卡、导航、来源锁、写删集合及输入描述；保存新稿与修订关联 | P4；独立生成／查看具体候选视图 |
| 审阅与固定检查 `hs-knowledge-lint` | P5 的独立审阅指引和确定性质量检查；独立 formal／candidate lint；显式代码证据复查 | P5；人工 lint；固定 CI 复用其领域函数 |
| 安全落位及收尾 `hs-knowledge-apply` | 内容／记录事务、完整 P7、仅索引重建／核验／回归／启用、事务恢复、本批提交清单和显式提交核对 | P7；消费端索引维护；事务恢复；只读提交核对 |
| 查询与同代精读 `hs-knowledge-query` | 按用途／范围／Claim 资格检索、receipt 和同代 read，直接核对当前来源及限制 | 独立 query／read，不依赖生产端通过票据 |
| 项目入口与准备 `hs-knowledge-explore` | 任务路由、按需依赖准备、项目发现、执行端连接提示、首次代码图谱准备 | 业务链之外的按需入口，不变成每次 ingest 的必走节点 |
| 维护与引用巡检 `hs-knowledge-maintain` | 来源／代码变化登记、机械限制观察和解除、事件恢复、独立引用差异巡检 | 跨批次维护；同名 lint Workflow 的引用巡检节点 |

正常主线的 5 个包为 source-scan、change-plan、view-materialize、lint、apply。独立 lint 没有再占一个包；query、explore、maintain 不因此被删除。

保留 maintain 的原因是它既有只读观察，也有独立的限制状态写入和事件恢复；这些操作跨越一个 ingest 批次。把它们塞进只读 lint 会混淆副作用，把它们全部塞进 scan 又会恢复 P1 的全库维护重负。

## 2. 现有 18 个 Skill 的逐包决策

“合并后删除”指目标能力和替代入口完成并满足本计划删除条件后的最终状态，不是本轮删除授权。现行动作以当前公开文档和实现为准；目标动作名是待锁定建议。

| 序号 | 当前 Skill | 最终决策 | 必须保留的动作／职责与不变量 | 新归属及独立入口替代 | API／模板／测试去向与删除条件 |
|---|---|---|---|---|---|
| 1 | `hs-knowledge-source-scan` | 保留并扩展 | `scan/prepare/record/status`；范围、真实 hash、扫描完整性、处理历史、欠账、缺口与本机收尾观察；无变化不制造记录 | P1/P2/P6；吸收 capture、resolve、resolve-source 的公开用途 | 更新本包请求、scan/material/record/status 产物与现有测试；输入未检查不得默认为维护已完成；详见第 3.1 节 |
| 2 | `hs-knowledge-change-plan` | 保留并收窄 | `plan` 的作者判断、六种卡动作、所有单元处置、旧 Claim 去向和原冻结查询；不由脚本发明结论 | P3；原 `review` 归 P5；字节 `run/verify/rederive` 的必要装配归 P4 公共函数 | 本包保留 semantic plan 契约和计划测试；review-result、审阅指引迁 lint；不再保留 4 轮字节计划计算作为公开主线 |
| 3 | `hs-knowledge-view-materialize` | 保留并扩展 | 一次生产确切视图、展示字节、导航、来源锁、写删范围、输入／原文件指纹；正式区不变 | P4；吸收字节计划装配、修订及视图说明 | 本包维护统一生产／修订 API、视图／修订／预览模板与对应测试；不得用调用旧 plan CLI 的方式完成迁移 |
| 4 | `hs-knowledge-lint` | 保留并扩展 | 现有 `lint/run/check` 别名、formal/candidate 模式、full/local 范围、0/1/2 协议；纯文档免代码核验；代码记录、证据与 current/historical 区分 | P5 和独立 lint；吸收 local-check、merge-check 的质量核验；CI 仍直接用可信领域函数 | 保留原报告协议，补 P5 Agent 指引／审阅记录、代码核验输入与独立复查设计；不把 CLI 变成 LLM、写卡或 Git 执行器 |
| 5 | `hs-knowledge-apply` | 保留并扩展 | `run/inspect/resume/rollback/verify-result` 的事务用途；增加完整批次与仅索引入口；写锁、CAS、备份、journal、回读、原代次及查询绑定 | P7；吸收 recover、index-build、query-regression、publish-handoff | 本包补批次／索引／恢复／提交核对 API、结果和测试；新旧入口真实检查层次分别说明，不能将安全写入冒称完整质量审查 |
| 6 | `hs-knowledge-query` | 保留 | 默认 search、`search/read/receipt`；用途／范围过滤、源与依赖资格、正式与 evaluation 区分、原搜索绑定、活动代变化后的同代读取 | 独立消费；来源与索引核验调用公共函数，不启动已删 Skill CLI | 保留 public-api、receipt 模板、用途／代码范围／材料／来源运行错误／公开回执测试；缺来源、超时、零命中不能混同 |
| 7 | `hs-knowledge-explore` | 保留并更新路由 | 只读发现、按需 setup、实际 config 映射、连接提示及首次 CodeGraph；空模块不虚构源码，不把提示当远端就绪 | 链路外的项目入口；路由到最终 8 包及两个 Workflow | 更新 SKILL 路由、public-api/setup 指南和发现／setup 测试；清除被删包指针；保留私有连接配置边界 |
| 8 | `hs-knowledge-maintain` | 保留并消除嵌套 CLI | `inspect-context/audit-references/register-source-change/register-code-change/recover-events/status/advance`；观察与写状态分离，historical 恢复语义、限制传播、事件持久化和锁 | 独立维护；现 lint Workflow 的 audit 节点仍调用本包 | 保留 request、普通结果及 audit 专用产物／指南、context/audit/event 测试；内部来源解析改公共函数；不得失去只读／写入边界 |
| 9 | `hs-knowledge-source-capture` | 合并后删除 | raw／附件／配置内源码捕获，显式编码／版本，固定提取适配器、hash/size/locator、精确历史恢复；`resolve/resolve-source` | source-scan 的捕获／备料／解析动作；公共 source_resources／提取函数供 query、maintain、P7 同进程复用 | request、提取与代码捕获指南、capture/resolve 产物及三组测试迁 source-scan／领域测试；删除条件 D1 |
| 10 | `hs-knowledge-candidate-inspect` | 合并后删除 | 精确显示字节／视图／计划绑定、路径与基线、类型识别、未结束事务定位；原 full checks 不丢，但只在 P5 运行 | 生产一致性归 P4、业务质量归 P5、写入安全归 P7 | 技术检查说明和结果字段按职责迁 P4/P5/P7；CLI／journal liveness 用例拆迁；删除条件 D2，不整体复制重放链 |
| 11 | `hs-knowledge-candidate-revise` | 合并后删除 | 新 operation、新材料／计划、明确 revision_reason、previous_view 关联、旧稿只读、修订后重新审阅 | P2/P3 的返回路径和 P4 修订生产动作 | revision 请求／结果／模板、用户纠正与 CLI 测试迁 P4及跨包测试；删除条件 D3 |
| 12 | `hs-knowledge-local-check` | 合并后删除 | `run/merge/verify-proof` 的逐 Claim 理由、确切代码／配置／Target／材料绑定、纯文档豁免、mixed 分区、current/historical 和 retired 语义 | lint 的 P5 固定代码证据检查及显式独立证据核验；公共代码上下文／证据函数 | review-guide、semantic_review 契约和结果说明迁 lint；local/module/public-code-gate 用例迁 lint／领域；删除条件 D4 |
| 13 | `hs-knowledge-merge-check` | 合并后删除 | 显式最新代码复查、确切 view/context/Claim 理由与源码范围；不是 Git merge，也不是当前固定 CI | lint 的显式代码复查动作；CI 仍使用领域 check.py | compatibility 和 merge 检查测试迁 lint 的独立复查说明／测试；不继续保留一层委派壳；删除条件 D5 |
| 14 | `hs-knowledge-governance-handoff` | 合并后删除 | 当前默认动作只描述 view、来源集合、基线、context 和续办提示；不批准交棒或写入 | P4 可选视图说明输出；OpenFlow 决定交棒 | handoff 请求／展示字段和 CLI 用例迁 P4；旧 handoff 保留原字节；删除条件 D6 |
| 15 | `hs-knowledge-publish-handoff` | 合并后删除 | `run` 的确切 commit_files／写删清单；`verify-submission` 对实际 HEAD/commit/blob／删除及变更范围的只读核验；不 Git 写入 | apply 的完成清单和显式提交核对动作；不成为 P7 成功前置 | result、submission-result 及写法／边界说明迁 apply；publish 用例迁 apply；删除条件 D7 |
| 16 | `hs-knowledge-index-build` | 合并后删除 | 默认 build、`build/verify/activate`；不可变代次、完整数据库／正文一致性、local/shared、code_contexts、原 expected_active、事务屏障、启用观察 | apply 的仅索引重建／验证／启用动作；公共 indexing、代次与可选发布身份函数 | shared-publication、manifest／结果规范和全部 index 测试迁 apply／领域；消费端无 view 仍能建索引；删除条件 D8 |
| 17 | `hs-knowledge-query-regression` | 合并后删除 | 默认 run 及 `verify`；固定 generation、非空 cases 和明确预期（允许显式空 expected_order）、purpose/context、无截断、逐命中同代读取、失败不启用、原 CAS 基线 | apply 的完整 P7及独立回归／复验动作；公共 query／regression 函数 | public-api、query_regression 结果和测试迁 apply／领域；query 保留正常 search/read，不负责写活动指针；删除条件 D9 |
| 18 | `hs-knowledge-recover` | 合并后删除 | 默认 run 的 mode 委派和 `inspect/resume/rollback`；原 journal／备份／视图、外部修改保护、committed 不回滚 | 直接使用 apply 的原事务动作；不再启动兄弟 apply CLI | 恢复指南、result 展示和 test_recover 迁 apply；旧不完整事务有可用原版本恢复路径；删除条件 D10 |

上述计数为 8 个保留包、10 个合并后删除包，共 18 个；不把同名 lint Workflow 当作第 19 个 Skill。

## 3. 保留包的目标接口和不变量

### 3.1 扫描与备料

现有 `scan/prepare/record/status` 保留。建议增加 `capture/resolve/resolve-source`，以接替原 source-capture 的独立入口；具体命名待锁定。

- `scan` 负责实际文件路径、字节指纹、同范围完整性和处理欠账。维护未检查、停点未核实必须明确，不把缺字段当作无义务。
- `prepare` 准备本批原文、相关旧版本、旧卡及依赖。当前文档／源码捕获、原版恢复和提取由公共函数完成，不调用 source-capture／maintain CLI。
- `capture` 的独立代码用途仍接受真实模块范围和指定文件；不扩大为扫描整个代码根，不发明 Target、宏、版本、构建或运行成绩。
- `resolve` 核实明确 bundle；`resolve-source` 按指定 source/snapshot/locator 解析，正式来源不得隐式取 latest。
- source change 的事件登记仍属于维护规则：捕获实现可以在同进程调用公共维护函数，但必须显式说明其副作用，不能把“capture 从不写任何业务状态”当成新保证。
- `record` 机械转写 P3/P4 已有处置，做新对象结构和绑定检查；不重判内容，不要求上游 passed 票据，不写正式记录。
- `status` 只观察事实和未知，不恢复或启用。消费端没有他人的本机日志时，不产生恢复生产者私有操作的义务。

捕获／解析迁移还须显式保留以下现有输入和恢复边界，不只保留一个“capture 成功”动作：

- raw 限六类允许目录；主 MD/TXT 为非空 UTF-8，PDF 每页需要文本层，DOCX 保留段落／表格及视觉缺口说明，附件显式列入。没有 OCR、URL获取、主动内容执行或改写原件。
- 定位保留 lines/page/paragraph/table_row 及代码 bytes 等各自语义；代码 bytes 是零起点半开区间，可覆盖空文件，不能把它冒充文本定位或语义支持。
- 源码默认行为与显式 `text_encoding:utf-8|gb18030` 分开，不猜编码，不转码原文件；固定派生文本／locator 和适配器身份。版本标签只记录明确材料和原类型，不把版本／模块标签当当前适用性。
- 一个捕获 operation 只拥有一份不可变 bundle；多原件分别捕获后再汇总，不能因合包用同一路径覆盖单件或材料汇总结果。
- exact source 返回原件／快照／定位、限制和 `current_source_matches:true/false/null`。历史可恢复不等于当前有效，缺当前授权不能吞掉确切旧证据；读取失败不变成正常零命中。
- Git恢复根来自实际配置，读取确切本地对象；不让来源指定任意仓根，不隐式 fetch／追踪改名／执行hooks，不修改全局信任。登记路径或允许的有界本地历史查找只接受 hash 和 size 同时匹配，不找任意替代文件或隐式 latest。
- 缺生产者缓存时，仅能由确切 Git／登记路径原版重现固定提取和 locator 指纹；不兼容或截断历史保留缺口。当前本地 evidence fallback 与跨工作区可恢复性是两种事实，不混为一谈。

当前依据：[scan 的公开请求](skills/common/knowledge/hs-knowledge-source-scan/references/request.md)、[capture 的完整来源边界](skills/common/knowledge/hs-knowledge-source-capture/references/request.md)。

### 3.2 内容计划与完整稿件

内容决策包保留 P3 的 `plan`。提前独立 `review` 的审阅行为及结果契约迁 P5；P4 字节 `run` 和 `verify/rederive` 的实际装配逻辑迁完整稿件包的公共装配函数，不在新主线保留公开反复推导链。

P3 仍需覆盖原件与独立维护单元、每条旧 Claim 的 preserve／修改／退役去向、六种卡动作及明确目标查询。P4 不能代作者发明处置，也不能以“实现简化”丢掉 merge/split 的 Claim 映射。

六动作的基数和目标边界也保留：create/update 各一个实际稿件，merge 有主卡与被替代 ID，split 有多个新卡和旧卡，deprecate 保留原身份及退役去向，defer 不夹带正式写入。旧 ID 不改写到另一个卡路径；控制文件和其他 ID 不能被 create 覆盖。merge/split 逐旧 Claim 映射，优先使用 `CardID#ClaimID`，歧义不靠猜；preserve 保留原正文／定位、有效范围、来源与核验字段。质量规则在 P5核对，不能因它们不再处处重复执行就从新设计删除。

P4 建议一个正常生产动作和一个显式修订动作，动作名待定。两者都生成确切视图；修订动作绑定旧 view、新 operation 和理由，输入变化时取得新材料，旧视图及历史报告只读。P4 的输入指纹描述实际材料，不是审查通过票据。

当前依据：[P3 与字节计划的区别及六决策规则](skills/common/knowledge/hs-knowledge-change-plan/references/request.md)、[materialize 的实际输出](skills/common/knowledge/hs-knowledge-view-materialize/scripts/materialize.py)、[修订的实际约束](skills/common/knowledge/hs-knowledge-candidate-revise/scripts/revise.py)。

### 3.3 审阅与 lint

保留既有 lint 只读 CLI 和 0/1/2 报告协议；P5 的 Agent 指引承接完整独立审阅。现有 CLI 模式是 formal/candidate，固定 CI 由领域脚本使用公共函数，不伪造一个已存在的 CI CLI 模式。

建议独立代码复查／历史证据核验动作供原 local-check、merge-check 用户迁移，名字待定。它们核验当前实际代码或确切旧证据，并报告真实层次；不启动 LLM、编译、运行程序或 Git merge，不认证 reviewer 身份，也不使报告成为流程票据。

保留逐 Claim 的非空理由、source/snapshot/locator/hash、配置范围、静态／build／runtime 证据要求、mixed 中只检查代码分区、纯文档免代码检查、retired 与 supported 的区别。历史记录不能通过重新签名或补字段冒充新复查。

当前依据：[原 lint 说明](skills/common/knowledge/hs-knowledge-lint/SKILL.md)、[原代码核验说明及指南](skills/common/knowledge/hs-knowledge-local-check/SKILL.md)、[merge-check 的真实兼容范围](skills/common/knowledge/hs-knowledge-merge-check/references/compatibility.md)。

### 3.4 安全落位、消费端索引和提交核对

建议在已有 apply 增加完整批次动作，以及仅索引构建／核验、独立回归／复验、启用、提交清单／核对等明确动作；名字和参数分组待锁定。它们不是新的 Skill，也不是所有动作互相必经。

| 独立任务 | 允许要求的业务输入 | 明确禁止的附加义务 |
|---|---|---|
| 完整 P7 | 本批具体 view、待入库记录、输入指纹、冻结查询及恢复事实 | 不要求新的 Workflow 身份、上游 passed 票据或自动 Git 发布 |
| 消费端仅重建索引 | 实际正式卡、规则、来源锁、适用源码／材料、local/shared 选择；启用／回归所需的明确查询输入 | 不要求生产者 view、P3/P6、apply-result、复核票据或本机私有缓存；不写知识／来源锁／正式处理记录 |
| 验证已有候选代 | 明确 generation，实际数据库／正文及所需业务材料 | 不重新 ingest，也不把“manifest 摘要正确”当成完整库验证 |
| 独立回归／报告复验 | 固定 generation、明确 cases，或有明确业务绑定的 view 查询；复验给确切报告 | 不以无关案例替换 ingest 冻结预期；只复验不自动启用 |
| 启用候选代 | 该代原 expected_active、实际内容／epoch、所需回归与启用事实 | 不拿新活动指针改写原基线，不把查询通过当成启用已发生 |
| 恢复事务 | 原 operation/journal/view/备份与当前目标字节 | 不用新 operation 冒充原事务恢复；committed 修改走新修订 |
| 本批提交清单与提交核验 | 本批确切 view／落位结果、记录及明确真实 commit | 不代替用户执行 commit/push/merge，不声称远端接纳或 CI 成功 |

仅重建可以先保存未启用的候选代；若请求同时回归／启用，必须有明确的实际断言及原活动指针。不能因为消费端没有 P3 就制造一份 P3 计划或任意查询来取得通过。

新 P7 主线不重跑整库质量 lint。索引公共函数也须拆开当前完整质量审查与索引自身所需的解析／数据库一致性，避免从 index-build 重新引入全库 `validate_card/validate_relations`。P5 一次临时索引检查，P7 一次正常连续执行中的实际代次全验；启用保留实际指纹、状态和 CAS。恢复后重新读取的候选代需要实际核验，不能继承已消失的内存结果。

写前输入基线与写后候选代基线分别描述：P4 固定旧正式集合和输入；事务按 view 写入后，候选代固定实际写后集合。启用比较后者，不能把自己的正常落位误判为输入漂移。

现有 `run/inspect/resume/rollback/verify-result` 可以在迁移窗口保留原事务行为，不能悄悄改变旧成功语义。最终新接口的事实层次须按实际检查更新；新安全写入动作不宣称执行过 P5。旧接口不构成长期保留被删 10 个独立包装包的理由。

当前依据：[apply 已有动作](skills/common/knowledge/hs-knowledge-apply/SKILL.md)、[索引及 shared 发布数据边界](skills/common/knowledge/hs-knowledge-index-build/references/shared-publication.md)、[回归明确预期和复验](skills/common/knowledge/hs-knowledge-query-regression/references/public-api.md)、[提交清单与真实 Git 核对](skills/common/knowledge/hs-knowledge-publish-handoff/scripts/publish.py)。

### 3.5 查询与项目入口

查询仍保留 search/read/receipt，正式 read 可以沿原搜索回执读取原代次；活动代变更不能偷换原命中，evaluation 候选不能冒充正式结果。来源恢复从公共函数取得，shared 代次的 Git／可选发布身份核验也直接复用公共函数，不再调用来源或索引 Skill 的 CLI。

来源不可得、当前条件不符、超时／运行错误和正常零命中保持不同结果语义。当前代码／配置／材料变化仍在实际使用时核对，不用 P5、apply 或旧 review 结果替代。

explore 保留任务路由、setup、发现和首次 CodeGraph。被删包的独立用途必须在路由表有新目的地；已有有效环境和上下文直接复用，不因包收敛增加安装登记或每次初始化。

当前依据：[query 回执与同代读取 API](skills/common/knowledge/hs-knowledge-query/references/public-api.md)、[explore 入口及路由](skills/common/knowledge/hs-knowledge-explore/SKILL.md)。

### 3.6 维护的读写分界和 lint 巡检

maintain 公开动作保留，不合并到 lint 或 scan 默认动作。

| 动作 | 读／写边界 | 不能丢失的条件 |
|---|---|---|
| `inspect-context` | 只读来源／卡／配置及现有状态，输出影响与缺口 | 按 Claim 用途解释来源；historical 确切旧证据可恢复时，不因当前字节漂移产生当前修订义务；真实缺口及语义限制仍保留；只沿明确 requires/derived_from 传播，不沿普通相关链接扩散 |
| `status` | 只读已登记限制和未完成事件 | 未观察不作通过，不推进水位或清除限制 |
| `audit-references` | 读取正式引用及可选 lint 报告，只写本次报告／派生产物 | 不写卡、锁、事件、水位和活动索引；failed/incomplete 的固定报告仍如实汇总；报告生成成功不等于全库健康 |
| `register-source-change/register-code-change` | 在同 K 写锁／本地状态 CAS 下登记确切事件和机械限制 | 来源身份、旧新快照、实际代码范围、先持久限制后发布事件；重复相同变化幂等 |
| `recover-events` | 补全已有 durable pending 事件 | 使用原事件、原快照与确切对象；材料缺失保持阻断，不补造或丢掉 pending 状态 |
| `advance` | 重查实际引用后解除已解决的机械 freshness 限制 | 不要求 apply/query/review 票据；不能借字节匹配解除语义／适用性限制，不宣称内容复核完成 |

当前同名 lint Workflow 的 `audit_references` 节点调用 `hs-knowledge-maintain --action audit-references`，见[现行编排](workflows/common/knowledge/hs-knowledge-lint/workflow.yaml)。保留这一独立入口；不得因为新 ingest 主线只剩 5 个主包，就使巡检第二步找不到能力。巡检的两个 Workflow 节点由 OpenFlow 传报告，不由 lint Skill 再启动 maintain CLI。

维护中的来源解析改为公共函数。保留事件／状态、普通结果、audit-result 及只读巡检各自契约，不能把普通结果模板当 audit 报告替代物。现有 `logs/events/state.json` 的同 K 锁／本地 CAS 不等于跨 clone 合并；本迁移不承诺自动合并多人限制状态。

维护动作只校验本职实际引用、材料和状态写入条件，不借公共函数再跑一套全库质量 lint；无法形成可靠机械判断时保留未知／限制。未完成事件可能仍引用本机证据，迁移或发布前须完成或保全其确切材料，不能随删除能力包清理运行目录。

当前依据：[maintain 动作及限制](skills/common/knowledge/hs-knowledge-maintain/references/request.md)、[事件持久化、恢复与 advance 实现](skills/common/knowledge/hs-knowledge-maintain/scripts/maintain.py)。

## 4. 10 个删除决策的逐项完成条件

下表是后续实施时要取得的证据，本轮未执行。目标包存在、函数改名或 import 能通过，都不足以独立判定迁移完成。

| 条件 | 原包 | 删除前必须可验证的行为 |
|---|---|---|
| D1 | source-capture | 经 source-scan 新公开动作完成 raw、显式附件、模块源码捕获和 bundle／单 source 解析；UTF-8 与显式 GB18030 保持确切原字节和固定提取指纹；旧原件通过可用 Git／登记路径精确 hash/size 恢复，缺版本／缓存／授权分开报告；query／maintain／P7 不再调用旧 CLI；捕获导致的变化事件没有丢失 |
| D2 | candidate-inspect | P4 产物身份／字节／写删范围／输入绑定仍可核对；P5 覆盖原质量规则；P7 阻止未恢复事务和基线冲突；不再通过 plan verify→rederive 或重放 materialize 核验相同稿件；独立 view 说明能读出必要字段 |
| D3 | candidate-revise | 用户纠正及 reviewer 退回能形成新 operation、理由、旧 view 关联和新内容；必要时重取材料／判断；旧报告不可改绑；all-deferred／无内容分支仍保留处置；重新通过 P5 后才按正常流程写入 |
| D4 | local-check | P5及独立 lint 检查正反例覆盖逐 Claim 理由／证据、实际模块、未知版本、Target、build/runtime 材料、mixed、纯文档豁免、retired、current/historical；旧复查结果可解释，不重签历史；不隐式执行编译或运行 |
| D5 | merge-check | 显式最新代码复查有新的 lint 公开用法；更改源码／配置能被发现；历史复查不偷读当前文件代替旧证据；CI 不引用旧包；不保留新的委派包装或 Git merge 副作用 |
| D6 | governance-handoff | P4 可输出同一 view 的计划／来源／基线／context 摘要和引用；缺确切视图明确报错；报告只描述数据不认证角色／交棒／批准；Workflow、模板、指南不再要求旧 handoff 文件作为前置 |
| D7 | publish-handoff | apply 完成输出或独立动作提供精确写删及正式记录清单；显式提交核对读取实际 HEAD／commit blobs、删除和提交变更范围；无关文件／旧 HEAD／字节不符被拒绝；不执行 commit/push/merge；记录批也有正确清单 |
| D8 | index-build | 没有生产端 `.build`、journal、证据缓存和 artifacts 的消费副本可用 apply 的仅索引入口建库／全验／启用；不重新 ingest、不写正式知识；local/shared、规则不兼容、code_contexts、可选发布身份、未完成事务、基线／epoch／活动指针冲突和回读保护仍有明确结果 |
| D9 | query-regression | apply 的独立回归／复验接受确切 generation 与明确 cases，保留用途、范围、命中／排除／顺序、Claim 断言、无截断和逐命中同代读取；失败不启用；verify 不启用；正常 ingest 不替换 P3 查询；保存报告与真实启用事实分开 |
| D10 | recover | apply 的 inspect/resume/rollback 可直接恢复相同原事务；部分写入、未知结果、备份损坏、外部修改、旧规则、rolled_back 和 committed 分开处理；SSH 断开不触发盲目重放；未完成旧操作有原配套版本可用，不要求保留新的 recover 包 |

## 5. 公共函数的归属与禁止事项

| 公共逻辑 | 主要使用者 | 目标归属／约束 |
|---|---|---|
| 文件读取、路径和配置映射、规则加载、指纹 | 所有保留入口 | 复用 `governance/contracts/validation.py` 等当前公共层；只做本动作必要检查，不附加上游身份系统 |
| raw／源码提取、精确来源恢复和 locator | source-scan、query、maintain、lint、apply | 基于现有 source_resources 及当前捕获实现提取公共函数；读取和捕获副作用分开；不从来源内容取得联网或执行授权 |
| 作者计划与字节装配 | change-plan、view-materialize | 作者判断数据与确定性字节生产分开；只保留一次本批视图生产，不新增一个重演旧节点的通用执行器 |
| 代码复核记录、范围和证据类型 | lint；query／P7只取实际需要的使用时指纹或资格函数 | 完整质量判断在 P5；区分只读当前使用资格与全库 lint，不以 shared helper 为名在每个阶段重跑全套检查 |
| 临时 lint 检查和固定 CI | lint、领域 check.py | 复用 checks；P5仅一次正常完整检查；CI的可信代码与输入边界单独维护 |
| 事务安全和恢复 | apply | 当前事务实现留在拥有者包或真正多调用者的公共层；不为形式统一把全部事务搬成可随意调度的插件引擎 |
| 索引格式、代次、同代正文、实际查询、回归 | apply、query；lint只使用临时索引函数 | 复用 indexing 并按必要调用者提取代次／查询／回归算法；独立入口控制写指针；不能通过导入已删包私有脚本保留依赖 |
| 事件状态、影响传播和机械限制解除 | maintain；source-scan 捕获路径有明确事件副作用时 | 基于维护规则提取必要公共函数；登记、只读观察、恢复和解除的副作用分别声明 |

实际模块名、函数签名和新增公共文件在实现设计中锁定，不在本规划中假装已有。公共函数是算法复用，不是另一套登记表、RPC、子进程桥或 Workflow run 证明。

## 6. API、指南、模板与测试的迁移清单

### 6.1 文档和模板随职责迁移

| 原资产组 | 新归属 | 处理方法 |
|---|---|---|
| source-capture `references/request.md`、result、提取／捕获说明 | source-scan references 与 capture/resolve 产物契约 | 合并原 scan 请求说明的重复公共参数，保留来源格式／编码／恢复边界；不把全部旧文档原样复制一遍 |
| change-plan review 指引与 `artifacts/review-result.yaml`、local-check 的 `references/review-guide.md` | lint 的 P5 审阅指南及确切审阅记录契约 | 同一份权威指南覆盖计划、实质 skip、成稿和必要代码；修复现有指向将删除 local-check 的链接 |
| change-plan 字节计划、candidate-inspect、candidate-revise、governance-handoff 的 request／结果／展示字段 | view-materialize 的生产、修订、视图说明契约 | 保留真实业务字段，去掉已删除的前置节点／重放／通过证明叙述；历史产物 schema 不重写 |
| local-check／merge-check 的结果、current/historical 证据说明 | lint 的独立代码复查和固定报告说明 | 保留结果层次与适用边界；不把结构核对描述成身份认证或技术真理判定 |
| index-build `shared-publication.md`、query-regression `public-api.md` 与结果字段 | apply 的独立索引／回归参考及公共索引格式说明 | 明确消费端无 view 用法、实际代次／原 expected_active、独立 verify 不启用；query public-api 保留引用 |
| recover 结果／恢复指南、publish-handoff result／submission-result | apply 的事务恢复、完成清单与提交核对参考 | 减少重复模板；事务 committed、整批 complete、submitted、远端／CI未知分开表达 |
| maintain 普通 result 和 audit-result、audit-writing/review 指南 | maintain 原职责内保留 | 不与 lint 固定报告互换，不丢巡检返回的实际 report_ref 和执行端产物位置 |
| explore 路由、根入口示例、知识根指引、使用说明、Workflow 及布局 | 各自现有位置 | 指向最终包和动作；项目入口仍只提供位置与路由，不复制全部领域规则 |

### 6.2 测试随公开行为迁移

所有以下项目是后续验证计划，未在本轮运行。被删包的测试目录不能跟包一起删除后仅靠总计数证明功能保留；先迁有效行为，删除只验证旧委派实现的断言。

| 现有测试源 | 目标测试责任 |
|---|---|
| source-capture `test_cli.py/test_code_capture.py/test_workspace_capture.py` | source-scan 新公开捕获／解析 API；公共来源恢复／编码函数的独立预期；保留无缓存精确历史恢复与授权缺口反例 |
| candidate-inspect `test_cli.py/test_journal_liveness.py` | P4身份／字节一致性；P5质量错误；P7事务屏障。重放兄弟 CLI 的实现断言改为不产生旧执行依赖 |
| candidate-revise `test_cli.py`；现有 post-ingest-correction 联检 | P4新 operation／修订关联及 P2/P3/P5 返回；旧正式事实与历史摘要保持 |
| change-plan `test_v3_plan.py/test_v3_flow.py/test_review_preserved_claim.py` | P3作者计划／处置和 preserve 语义，P5审阅覆盖；字节装配用例迁 P4 |
| local-check `test_local_check.py/test_module_mapping.py/test_public_code_gate.py`；merge-check `test_merge_check.py` | lint 的正反代码证据用例与独立复查，不继续依赖被删包加载；保留确切模块／Target／材料及历史用途边界 |
| governance-handoff `test_cli.py` | P4可选视图说明；输出不认证交棒 |
| publish-handoff `test_publish_handoff.py` | apply 的本批清单／实际提交核对，记录批、无关改动和 Git事实缺失反例 |
| index-build 当前 tests 全集 | apply 的仅索引入口及公共 indexing：完整集合／行值、版本、同代正文、源码／材料／shared身份、journal liveness、跨工作区恢复等仍逐项有覆盖 |
| query-regression `test_cli.py/test_purpose.py/test_v3_gate.py` | apply 的独立／P7回归及复验；原查询预期和独立 cases 分开，失败不启用 |
| recover `test_recover.py`；apply `test_apply.py/test_public_governance.py` | apply 直接恢复与事务安全，新完整批次停点与旧事务动作语义分别验证 |
| query 当前 public receipt、purpose、qualification、live code scope、build materials、source runtime 测试 | query 原公开协议；仅把旧 sibling CLI 故障注入点改为真实公共来源执行边界，保留超时／缺口／零命中区别 |
| maintain `test_cli.py/test_context_inspection.py/test_reference_audit.py` | 原全部读写／事件／历史用途／巡检行为；不再以是否启动 source-capture CLI 作为正确性标准 |
| explore `test_cli.py/test_setup.py` | 最终路由和现有 setup／实际项目发现边界 |
| 领域 `test_clean_clone.py`、`test_manual_skills.py`、`test_node_pipeline.py`、Workflow／分发／索引契约测试 | 最终 8 包公开联检、正常 7 阶段与仅记录／no-op／修订／恢复，消费副本无生产端私有材料仍按实际业务数据工作 |

现有测试入口见[evals README](himate-knowledge-wifi-mp/evals/README.md)。后续调整测试分组、requirements、分发和测试脚手架时，以最终 8 包为准；不要通过给新包添加旧模块别名、动态 sys.path 或伪造旧 CLI 输出让旧测试继续绿。

## 7. 可执行的迁移依赖顺序

本节描述后续任务顺序，不授权本轮实施。

1. **锁定行为清单和新公开 API。** 确认最终 8 包、每个独立任务的输入／副作用／成功层次、新动作名、历史兼容和结果协议。优先定义消费端仅索引、独立来源解析、事件恢复及旧事务恢复，不能只定义正常 ingest。
2. **提取多调用者公共算法。** 来源、提取／locator、代码证据、字节装配、索引／代次、查询／回归、必要事件函数逐项建立明确边界。保留各拥有者入口的副作用控制。
3. **完成目标包替代入口。** source-scan 接捕获／解析，P4接字节生产／修订／说明，lint 接完整审阅／代码核验，apply接完整批次／仅索引／回归／恢复／提交核对；maintain／query消除 sibling CLI。
4. **迁资源与调用方。** 按第6节迁公共API、模板、指南和有效行为测试；同步 explore、两个 Workflow、布局、共享说明、分发器与规则／包锁。旧历史字节保持。
5. **按 D1—D10 验证删包条件。** 先冻结目标候选并取得对应公开入口证据，再从分发清单和安装清单删除旧包；在不含旧包的隔离安装验证，不能因开发仓残留旧目录而假通过。
6. **结束主动兼容包装。** 不再发布旧 10 个 Skill 作为空壳。旧规则未完成操作要么在删除前结束，要么明确保有可用的原配套发行版本；不是要求当前发行版永久携带旧包。

删除不能改变来源、正式卡、来源锁、处理历史、事件状态、旧 journal、回执和已保存报告；删包只涉及当前能力分发及其调用方的迁移。

## 8. 总体验收与发布前条件

| 检查对象 | 必须取得的实际证据 |
|---|---|
| 公开集合 | 新安装包恰有 8 个目标 Skill；路由和文档没有仍要求被删 10 包的可执行入口 |
| 执行依赖 | 保留 Skill 不启动其他 Skill CLI，不直接导入兄弟私有脚本；真实行为联检在不含旧包的安装下完成 |
| 正常 ingest | 七阶段；P5完整质量检查一次；P7同进程收尾；本批目标查询与实际启用均有事实 |
| 独立用途 | capture／source resolve、代码复查、正式 lint、query/read、消费端仅索引、独立回归／复验、事务／事件恢复、引用巡检、提交清单／提交核对各有公开入口正反例 |
| 修改与未知 | 缺材料、错误证据、源码／配置／规则／基线漂移、查询未达预期、响应丢失、未完成事务及外部修改不会被包收敛隐藏 |
| 跨工作区 | 只取正式资产及必要可恢复依据，不复制生产端私有运行目录，仍能检查、重建、查询和增量观察；缺旧版本或真实代码材料保留缺口 |
| 历史兼容 | 当前包不重签旧材料；原规则未完成事务有真实恢复方案；已 committed 不当作待写入，已 rolled_back 不重复恢复 |
| 性能与质量边界 | 记录逐阶段墙钟、进程数和实际等待；结构减少不等于固定提速，合成复核和索引检查不等于真实知识质量／宿主独立性／CI／权限验收 |

现有跨工作区机制依据见[clean-clone 测试源码](himate-knowledge-wifi-mp/evals/tests/test_clean_clone.py)与[详细设计 §6.4](himate-knowledge-wifi-mp/docs-llm-wiki/知识库详细设计.md#64-哪些内容上库哪些用于本机执行)。这些是现行行为与后续计划依据，本轮没有重跑、更新验收计数或声称新版已实现。

## 9. 主要风险和需要锁定的设计点

- **包变少但动作消失。** 最大风险是只实现 P7正常路径，漏掉消费端重建、独立来源恢复、历史复查、事件恢复或提交核对。以本计划矩阵和 D 条件逐项关闭，不用“已合并”一句话替代。
- **旧重链被搬进公共函数。** 不允许保留相同 plan 重演、整库重复质量检查和层层调用，仅把 subprocess 换成函数；公共函数必须按实际算法和副作用拆分。
- **读写职责污染。** lint 与 audit 保持只读正式状态，query 不启用指针，消费端仅索引不写知识，捕获／登记和 advance 的不同副作用必须显式。
- **接口兼容与历史恢复混同。** 当前发行版可删除旧 CLI 包，但已保存数据不能因此改写。原配套实现、记录格式解读和明确旧操作恢复路径须在删除前确认。
- **新安全动作被误报质量通过。** 新 P7的 `committed`、整批 `complete`、索引 `activated`、提交 `submitted`、语义复核、CI和远端合入分别报告；没有实际动作不能生成相应通过结论。
- **公共接口名字尚未锁定。** capture／resolve、完整批次、仅索引／回归／提交核对和独立代码复查的动作名、请求分组及结果格式须另做接口设计；本文不把建议动作说成现有能力。

最终决策建议：批准“8 个保留包＋10 个迁移后删除包”的目标，按独立用途先定义替代接口，再拆算法和收敛主线；不以永远保留兼容包装代替完成迁移。
