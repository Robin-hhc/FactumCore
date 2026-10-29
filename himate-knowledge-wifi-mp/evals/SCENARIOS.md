# 场景与测试职责

本表按行为及失败后果维护覆盖范围。用例数量、参数数量和某次历史通过数不能表示覆盖率。测试只使用隔离合成材料；完整集合以 `run_acceptance.py --profile full` 当次实际收集结果为准。

## 分层原则

| 层 | 适合验证什么 | 执行方式 |
|---|---|---|
| 契约与边界 | 状态、用途、来源引用、路径、字节绑定等组合规则 | 直接公共契约，保留独立预期和完整有效/无效矩阵 |
| 公开 CLI | 参数、结构化报错、真实输出、固定规则锁、进程边界 | 每个业务边界保留代表调用；负向场景只准备到它真正需要的前置条件 |
| 跨节点与持久化 | 文档/代码链、更新、真实 Git clone、进程中断、恢复和索引激活 | 全量保留实际 CLI、Git 或子进程；避免为每个字段组合重走整链 |

quick 是显式选定的契约与公开入口冒烟，只用于日常反馈。它不包含本表所有场景，不能替代交付前 full。默认仍为 full；未标注的新文件自动进入 full。quick 的文件清单在 [run_acceptance.py](run_acceptance.py) 的 `QUICK_FILES`，报告保存本次实际选择；缺少文件、空收集、收集错误和超时均不能算通过。

## 场景映射

Skill 测试目录均相对 `repo/skills/common/knowledge/`。本目录的 `tests/` 为领域及跨包测试。表中列出主责任位置，相关包仍可从自己的入口验证相同规则的接线。

| 场景 | 主责任位置 | 必须保留的观察与断言 |
|---|---|---|
| 无 catalog 文档完整入库、原件未变但明确修卡 | [test_manual_skills.py](tests/test_manual_skills.py) | 实际七阶段；每次 P1—P6 调用后正式路径及字节未变；P7 前新扫描仍待处理；P7 发布清理后 search/read 使用本批真实活动代；旧成功记录、原件未被改写 |
| 来源改动、旧 Claim 阻断、更新与旧指针保护 | [test_node_pipeline.py](tests/test_node_pipeline.py)、[test_post_ingest_correction.py](tests/test_post_ingest_correction.py) | 修改真实夹具字节，拒绝旧内容冒充当前；独立 build 不改变活动指针，恢复及修订后真实查询结果正确 |
| 代码证据链与补充符号引用 | [test_manual_skills.py](tests/test_manual_skills.py)、lint `test_public_code_gate.py` | 本地代码检查、实际材料绑定、入库及查询；缺证据或漂移必须拒绝 |
| code_ref 必填及符号导航 | [test_code_ref_required.py](tests/test_code_ref_required.py)、[test_code_symbols.py](tests/test_code_symbols.py)、[test_code_ref_contracts.py](tests/test_code_ref_contracts.py) | formal/candidate/ci × draft/stable × review_mode；插行、改体、删除、歧义、作用域、参数、宏/枚举；旧快照与当前导航分开判定 |
| 原件类别、附件与定位 | source `test_capture_cli.py`、[test_document_source_checks.py](tests/test_document_source_checks.py) | troubleshooting 与附件真实字节、PDF 页、DOCX 段落/表格、无法提取拒绝；定位不能越出原件 |
| 合并来源节点与独立动作 | source `test_run.py`、[test_source_node_pipeline.py](tests/test_source_node_pipeline.py)、[test_revision_roundtrip.py](tests/test_revision_roundtrip.py) | 八包安装下正常链真实调用一次source.run，再走P3—P7；无变化早停，独立scan/prepare等动作保留，P5补料只prepare且原scan字节不变 |
| 新扫描与旧私有记录隔离 | [test_staging_history.py](tests/test_staging_history.py)、lint `test_candidate_journal_liveness.py`、source `test_execution_history_boundary.py` | 未显式引用的执行历史禁止读取/遍历；正式与候选检查均不依赖它；公共入口保留垃圾历史哨兵与当前稿篡改拒绝 |
| P2 实际中断后另开工作流 | [test_ingest_stage_interrupt.py](tests/test_ingest_stage_interrupt.py) | 实际停止准备进程；正式库不变；新 operation 仍根据正式状态扫描，不能自动接管旧半成品 |
| P7 安全写入与保留输出槽 | apply `test_publication_cli.py`、`test_apply.py` | 真实 CLI 路径/保留槽矩阵；断言指定 guard 报错与全树原字节不变；成功自有 transport 另走真实发布与清理链 |
| P7 故障停点、清理失败重试及硬退出 | apply `test_p7_actions.py`、`test_publication_cli.py`、[test_process_recovery.py](tests/test_process_recovery.py) | 发布事实与整批完成分开；只补缺失收尾/清理；实际停止进程后的 journal 和确切视图恢复；原指针保护 |
| 索引完整性、冻结查询与首次 CAS | apply `test_p7_cas_and_verification.py`、[test_indexing_contract.py](tests/test_indexing_contract.py)、[test_publication_regression_binding.py](tests/test_publication_regression_binding.py) | 数据库全量内容校验；不能用自签 passed、替换查询或新指针重建旧基线；P5/P7 各自实际校验对象 |
| P5冻结查询前置与P3返工 | [test_p5_frozen_queries.py](tests/test_p5_frozen_queries.py) | 用途不兼容在P5阻断，正式区不变；修正用途的新轮可发布；已有活动代不能替代最终候选；P7保留实际回归 |
| 正式库巡检、只读与待维护限制 | lint `test_cli.py`、maintain `test_reference_audit.py`、source `test_completion_status.py` | 失败逐卡/Claim 可定位；读取不改正式内容；限制与待办不能误当 noop 或成功 |
| 来源/代码引用的当前与历史用途 | source `test_historical_context.py`、query `test_purpose.py`、`test_code_navigation.py` | current/guidance/history 的使用资格；来源顺序不能改变结果；改体与符号变动各自覆盖 |
| 查询内容和简洁地址、同代回执 | [test_query_output_contract.py](tests/test_query_output_contract.py)、query `test_public_receipt.py`、`test_code_navigation.py` | 外部响应及新回执不嵌入原件／展开引用；内部资格保持；Claim子集、旧格式及确切代内卡地址；不同文件的地址／摘要不得混配，缺失与歧义不伪造当前行段 |
| 导航旧空库说明修复 | [test_navigation_generation.py](tests/test_navigation_generation.py)、[test_manual_skills.py](tests/test_manual_skills.py) | 标准旧句在P4候选替换，自写说明与引用文本保留；P1—P6正式字节不变，P7发布已审导航；分发模板不固定断言当前为空 |
| 无生产端缓存的真实 Git clone | [test_clean_clone.py](tests/test_clean_clone.py)、[test_snapshot_checkout_recovery.py](tests/test_snapshot_checkout_recovery.py) | md/pdf/docx × 原件已提交/正式归档两条恢复路；静态代码 clone；无旧 `.build`/本地索引仍检查、重建、激活、查询与扫描；缺失/损坏正式依据拒绝 |
| 工作区、包与执行安全 | [test_workspace_mapping.py](tests/test_workspace_mapping.py)、[test_nested_workspace.py](tests/test_nested_workspace.py)、[test_git_read_isolation.py](tests/test_git_read_isolation.py)、[test_skill_call_timeouts.py](tests/test_skill_call_timeouts.py)、[test_workflows.py](tests/test_workflows.py) | 配置真实绑定、安全路径、非交互 Git 超时、规则锁及包边界、Workflow 静态契约；不执行来源内指令 |
| 测试入口与性能汇总自身 | [test_acceptance_runner.py](tests/test_acceptance_runner.py)、[test_benchmark_metrics.py](tests/test_benchmark_metrics.py) | 选择错误/空收集/超时不通过；部分输出落盘；环境和选择变化明确不可比；耗时增长始终只作提示 |

## 本轮去重与保留理由

- 原独立 `test_ingest_phase_boundaries.py` 的逐调用正式字节边界及 P7 前 fresh scan 已并入文档主链；同一整链不再因为 specs/troubleshooting 目录差异重复。troubleshooting 的输入类别及附件规则留在准备层，文档格式与两种恢复路径的真实 clone 矩阵完整保留。
- 文档主链直接验证 P7 产出的索引和查询结果，移除成功后重复的独立 build/regression。独立动作及不改变活动指针的断言仍在专用用例。
- 旧 journal 的状态/坏 JSON/坏 seal 等组合改为带文件访问哨兵的直接检查，明确禁止读取未引用历史。公共 CLI 仍验证代表场景，当前显式视图的损坏拒绝继续单测。
- transport 负向矩阵在业务 handler 前就应拒绝，省去 capture 和 final view；特定报错断言防止因为缺业务材料而误通过，原文件保留及不产生新文件均核验。
- code_ref 的一个完全重复单元已并入原 12 格矩阵，路径诊断在矩阵每格核验。便宜但对应不同约束的安全矩阵继续保留。
- 正式记录脱离缓存的测试清理使用严格的目录范围核对及 Windows 扩展路径，不忽略删除异常；输出前缀变长不应妨碍执行真正的业务断言。

## 增补用例时

先明确它要阻止哪种错误，选择能观察该错误的最低层。已有相同预期时扩展数据矩阵；增加完整 CLI/Git/进程链必须有新的跨边界观察。修改夹具不得自动重签发出的规则锁来让测试通过。共享可变规则或全局子进程替身容易掩盖隔离/恢复错误，保持每例可变材料隔离。

这些机制测试未验收真实 OpenFlow 角色隔离、公司 API、六 Target、CI 合入或 ACL，也不评价知识语义正确率。合并/拆分等语义决定有契约覆盖，不据此宣称每种业务决定都跑过实际七阶段整链。

## 真实仓验收

真实源场景由 Agent 在已授权的本地业务仓上单独发起，需要确切源码、文档及执行位置；自动 quick/full 继续使用隔离合成材料。源码原仓保持只读，新隔离副本固定实际版本及逐文件摘要，采用本次能力和发出的规则锁，新 operation 从空正式库起跑。

1. 读取实际 Skill/Workflow，P1 扫描原文，P2 准备原文及必要代码，作者按原文和代码做 P3 决定及 P4 成稿。记录每次 P1—P6 后正式路径与字节未变。
2. 独立 Agent 实读原文、代码、计划与稿件后调用 P5 review。保留真实来源引用及 code_ref 的状态，不用静态位置替代构建或运行证据。P6、P7 实际发布、检索收尾、激活和清理，核对正式 publication/completion 及已清理的旧 view/material。
3. 在出卡前由另一 Agent 只读源文档，固定自然语言问题、精确词控制、跨主题题及资料不足题。作者不看题面；查询者仅拿用户题面，先固定正常提词方案，再调用原句及提词查询。全程不按测试问题修改卡片。
4. 记录 raw 与提词后的排名、完整命中、空结果、阻断及耗时，通过真实 search 回执精读同代卡，并沿来源及当前导航回源。资料不足题检查能否明确拒绝编造答案；相关背景命中不等于该问题已有答案。
5. 分别报告本轮实际入库、用户检索与答案依据，核对来源和副本未改、固定检查及索引完整性。保留首次失败与后续修正的确切证据，真实源观察与合成测试计数分开。小库少量问题的结果不推广为大库召回率或知识正确率。

这验证人工逐 Skill 的真实数据链路；实际 OpenFlow 调度、编译、硬件和权限仍需对应现场证据。
