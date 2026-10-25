# 编排与公开协议交叉复核

依据：冻结详设 `baseline/知识库详细设计.md`（SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`）及 R301—R311。检查活动 Workflow、实际公开 CLI、固定检查与 shared 查询资格；未读取真实原件／知识正文或 gold，未改变批准设计和历史 SDD。

## 节点协议对照

Workflow 的 exit 是条件分支，部分名称是语义别名，不要求机械等于 CLI phase；调用方必须同时读取真实 phase、data 和固定产物。特别记录以下实际对应关系。

| 节点 | 公开调用与实际结果 | 编排核对 |
|---|---|---|
| P1 scan_sources | source-scan `--action scan` → scanned；data.scan_ref / actionable_unit_ids / affected_claims / context_gaps | E0在外；无raw变化但有affected Claim不能走无需更新分支；续办／恢复须读实际停点 |
| P2 prepare_material | source-scan `--action prepare` → prepared；material_ref / bundle_ref / gaps | 各状态来源候选、requires/derived_from扩展和逐卡旧版；显式code_bundle_refs经公开resolver核当前身份后才进入current_code，不以旧代码冒充新材料 |
| P3 plan_change | change-plan `--action plan` → content_planned，semantic_plan_ref | raw.units精确覆盖；maintenance_units独立绑定current_context，不伪造raw；目标cases随计划封存 |
| P3 review_plan | change-plan `--action review` → reviewed / needs_revision，review_status与skip_sample | reviewer_id不同作者，记录抽中和未抽；无产卡批仍经适用实质skip抽查后到P6 |
| P4 materialize_view | change-plan run形成plan_ref，再view-materialize → ready / deferred | 同一节点使用公开helper串起完整P4候选；视图需已固定卡、导航、lock及相关基线 |
| P4 review_content | change-plan review带view_ref → reviewed / needs_revision | 确切view_digest绑定；后续apply重新检查独立作者和无未解findings |
| P4 lint_preflight | lint CheckReport passed/failed/incomplete，exit0/1/2 | 单独协议不能当旧ResultEnvelope；全范围、完整报告；通过不替代P5 |
| P4 inspect_candidate | candidate-inspect → manual_ready / code_ready / **mixed_ready** / recovery_required | F1复核时发现的混合出口遗漏已补；mixed_ready明确到prepare_confirmation。v3内部也复用固定preflight，代码批须携带相同check_inputs.code_checkout |
| P4 prepare_confirmation / 真人gate | confirmation-prepare → awaiting_human等展示状态；gate需真实人明确答复 | 不以等待超时通过；完整确切view展示，原始host_event须由受信适配认证 |
| P4 record_confirmation | confirmation-record返回approved/rejected及manual_review_ref；不是phase=accepted | accepted分支表示实际approved；混合视图保留此manual proof，再到local_check；silence保持停点 |
| P4 local_check | local-check run → passed/failed/incomplete，data.check_status/local_check_ref | code_passed分支必须实际passed；混合只核code部分，manual proof仍保留 |
| revise_candidate | candidate-revise需新operation、previous_view_ref、新语义计划；→ready / deferred | 失效确认不重用；材料／计划问题返回P2/P3；旧apply事实不重写 |
| P5 lint_view | 与预检相同CheckReport协议，确切view_digest+full+complete+passed | 不在lint修卡／确认／apply；失败按finding回对应节点 |
| P6 record_ingest | source-scan record → recorded，batch_kind / ingest_record_ref | 此phase仅表示草拟记录已校验；status仍pending。raw处置与maintenance_dispositions分别精确覆盖，defer／failed欠账不会因无raw消失 |
| P7 apply_view | apply run → committed；data.batch_kind区分content与record_only | committed指本机事务，不能当Git commit。content需final lint_report_ref/content_review_ref/check_inputs并实际重跑；混合需proof_set的manual_document+code_gate两项；record_only不携知识写集 |
| P7 recover_transaction | recover inspect/resume/rollback委托公开apply；实际phase inspected/committed/rolled_back | recovered是语义出口，必须实际核原事务；record_only由batch_kind识别，不能重复apply |
| P7 rebuild_index | index-build build / verify，返回generation_ref与完整验证 | 此处是实际落位后的本机索引；运行故障仅重试收尾，内容错误需新修订操作 |
| P7 query_regression | query-regression从view/plan读取cases；通过后激活，verify可重演 | 不能用调用者空cases跳过；发布handoff重新验证actual report/generation |
| P7 publish_handoff | run → ready_to_submit / record_only_ready，commit_files及write/delete manifest | ready只进入提交节点，不代表已提交；记录批无index/query要求；content必须实际本批索引和目标查询已通过 |
| P7 submit_batch | 授权宿主提交精确清单，再 `--action verify-submission` + commit_sha → submitted | 验实际HEAD／Git对象、写删字节、差异只含batch；无真实授权／commit时pending，不把ready报完成 |

## 可复现问题

| ID | 现象与证据 | 影响与最小修正 |
|---|---|---|
| F1 | 公开合成capture→plan→materialize→candidate-inspect输出phase=mixed_ready、review_mode=mixed；当前inspect_candidate exit表无mixed_ready。重放脚本 `.scratch/knowledge-entry-research-20261024/reproduce_mixed_workflow_exit.py` 输出matching_exit=[] | R305混合路径应有明确mixed_ready→prepare_confirmation映射及分支测试。现manual_ready自然语言条件也可被Agent解释为混合，但不据此证明真实宿主会自动正确选路；当前确认的是声明图与公开状态不齐全 |
| F2 | records接受unit.progress对象；正式共享记录 `{status:skipped}`通过其契约后，source-scan公开scan退出2、INVALID_INPUT、unhashable dict。反例 `test_scan_accepts_valid_object_progress_from_shared_processing_record` 已RED | R302跨机增量不能因合法进度表达失败。pending_units与finished判断应归一化progress.status；不缩窄已经接受的共享契约 |
| F3 | 空正式库但现有sources.lock的snapshots是字符串broken，公开lint返回passed/exit0、6项全部通过。重放 `.scratch/knowledge-entry-research-20261024/reproduce_empty_lock_lint.py` | R306/R310固定检查漏掉真实格式错误。checks.run解析／schema异常仅在cards非空时登记，吞掉空库坏lock；存在的lock仍须按固定Schema失败，CI共用函数同样受影响 |

以上问题均在生产冻结时以只读重放／新增测试确认，并交root最终修复窗口；没有用推测的宿主运行结果当作重现。最终修复／复测状态应以本次统一验收记录为准。

最终窗口已修F1、F2：混合公开CLI路由反例先RED再GREEN，Workflow及真实固定OpenFlow loader共6 passed（17.32秒）；合法progress对象先RED再GREEN，source-scan全组13 passed（42.50秒，importlib模式）。原生产物合同仍按各node实际出口声明，没有改动上游loader／validator。4项unused import同时清除，相关ruff通过。F3由治理负责人修固定检查函数，并纳入root统一最终回归；本记录不代替其验收结果。

后续必要接点复核补齐了代码原版恢复：过去公开code capture即使实际代码已提交，仍只产生本机evidence_object，与P7必须实际可恢复的Git来源不相容。现按既有受信config/catalog及真实code_identity，只有HEAD blob与捕获字节一致才自动登记repo_id/commit/path并严格复核；dirty／export仍保留本机原版，不能借此进入正式库。无本机缓存的`.c`以冻结code-utf8:1规则重建文本及定位并比对摘要，不兼容时保持未完成。

历史可读与正式可移机分开：`recover_snapshot(...allow_local_fallback=True)`允许当前配置／Git不可用时读取精确本机历史副本；P7指定False，Git原版实际不可恢复时即使本机副本存在也不放行。code-capture公开自动Git反例先RED再GREEN，source-capture整包37 passed（45.67秒，隔离稳定规则fixture）；正例没有手改恢复指针。代码dirty捕获仍local与P7通用local／历史fallback拒绝链构成边界证据，不冒充真实六Target代码卡完整验收。

记录批关联知识并不构成知识写入：P6使用受控空写删视图，按共用契约从正式卡／Claim解析关联；既有稳定卡引用正例通过，虚构卡、虚构Claim及`.build`未通过稿件引用反例拒绝。实际知识／导航／来源锁三项写集合仍为空，defer保留blocked。共用formal+overlay与限制重建接口整合后，source-scan最终整包17 passed（54.10秒）；此前一次并行maintain修改被PACKAGE_CHANGED拦住，独立重放及最终冻结整包均通过，不将并行保护性拒绝作为功能验收。

P2代码捕获沿用单来源不可变操作边界：每个代码来源使用独立子operation，再以显式bundle引用由batch prepare聚合；Workflow提示和Skill引用说明已同步，避免占用同一个capture.json。代码签名、Target与构建材料的端到端测试仍属于合成验证层次，不能据此声明真实六Target已接入。

## 固定CI与shared资格复核

- `check.py`只从job指定trusted-root及其锁定hash读取运行器规则；通过固定字节loader导入，候选端只覆盖knowledge、导航、sources.lock与logs/ingest数据。候选目录程序／缓存不导入。CI source resolver要求显式source_objects，代码卡要求明确code_checkout；原文或代码缺失为未完成，输出目录不在输入树，前后数据摘要核对，不修输入。
- CheckReport覆盖固定check IDs，检查状态、findings、digest、rules、full scope和exit一致性；P7另实际重跑最终检查，因此调用者写一份声称passed的JSON不能授权入库。F3是现有实际规则执行中的漏检，不是用报告格式推导的假想风险。
- shared index读取受信publication签名与确切knowledge_commit，逐卡核Git对象及正式acceptance summary。sources.lock逐个**被引用**的resource+snapshot与Git版本比对，再将reference/resource/snapshot纳入qualification；不是拿整个可增长lock摘要当一张卡的资格。追加无关来源不应失效旧卡；改被引用版本不能借卡正文未变继续回答。
- query shared每次经index-build verify重验签名、Git卡字节、accepted record和per-reference来源，再单独判断当前代码/config。current与historical资格分离，同代检索／精读保留generation与card/body摘要。此次只读未发现这条逐引用校验存在可重现绕过；没有替用户暂缓的新search时效检查扩scope。

## 证据范围

实际OpenFlow固定源码loader与结构图检查证明文件合同可加载；public CLI合成重放证明上述协议状态及反例。真实宿主对条件分支的选择、真人授权适配、真实六Target、CI服务器作业权限和最终合入仍不由这些测试证明。本复核未新增部署方案或更换引擎。
