# 治理组交叉审查与公开反例

基线：V3 冻结详细设计 SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。审查覆盖新增索引构建／查询／M 与 P3/P4/P7 的公共链路及共用治理契约。未读取真实原件、正式知识正文或受限 gold；以下反例均来自隔离合成 fixture，未把签名 fixture 当成真实人、真实代码或远端 CI 验收。

## 已确认的问题

| ID | 位置、因果与设计依据 | 公开反例与修复要求 | 状态 |
|---|---|---|---|
| R1 / P1：不可读原件可以被 skip 标成完成 | `contracts/records.py:validate_ingest_record` 原来只限制 completed，允许 read_failed/read_error 单元产生 skipped/withdrawn；P1 完成集合包含 skipped，可能让未取得材料的事项进入已处置状态。违背 §5.2 固定清单区分读取失败、§5.5 缺材料不得通过。 | `evals/tests/test_governance_v3.py::test_unreadable_scan_unit_cannot_be_finished_by_substantive_skip`：带 Access denied 的固定扫描单元配自报独立抽查、action skip/progress skipped，原实现不拒绝（DID NOT RAISE）。现在对 read_error 或 read_failed 禁止 completed/skipped/withdrawn，必须 pending/blocked/partial。 | 修复已落，公开反例 GREEN。 |
| R2 / P1：P4 可以删除 P3 明确 preserve 的 Claim | `hs-knowledge-change-plan/scripts/planning.py` 原 v3 校验只确认 create/update 的 Claim 存在，忽略 preserve。旧卡两个 Claim，计划只修改一个、保留另一个，草稿却能删掉被保留项。违背 §5.3 逐 Claim 判断及保留其他适用范围。 | `hs-knowledge-change-plan/tests/test_review_preserved_claim.py::test_draft_cannot_remove_a_claim_that_the_authored_plan_preserves`：正确 RED 为公共 CLI actual exit 0 / phase planned，expected 2。需核对 preserve 的 ID、正文与范围等稳定事实，并拒绝未计划的 Claim 变动；不以内容审查替代这个确定性约束。 | 已交内容组，修复已落，最终公共回归核实。 |
| R3 / P1：本机来源锁可重指已接纳卡的确切原版 | `hs-knowledge-index-build/scripts/node.py:validate_publication` 对 Git 发布来源锁仅验证 source/snapshot ID；后续 query/source-capture 从当前工作树锁恢复。保持旧 snapshot_id，修改本机 sha/bytes/recovery，再把 raw 换成新材料，可使旧已接纳卡继续 current 命中。违背 §5.9 确切依据恢复、§5.10 当前来源比较。 | `hs-knowledge-index-build/tests/test_review_source_lineage.py::test_published_reference_rejects_retargeted_local_snapshot`：受信合成签名、真实 Git 卡／规则／验收记录保持不变，只替换本机相关来源锁和材料，原 query exit 0 且返回 lineage-rule。应按每张卡实际引用比较 Git 接纳的 Resource/Snapshot 与当前 resolver 所用对象，差异 SOURCE_LINEAGE_MISMATCH；允许无关来源追加，不能要求整份锁 hash 恒等。 | 已交 root，逐引用谱系修复已落，最终回归核实。 |
| R4 / P1：Windows 长输出路径令恢复成功却没有公共结果 | family2 `scripts/support.py:atomic_bytes` 未使用扩展路径；公共恢复输出 263 字符时真实 os.replace 抛 WinError 3，recover 包只能报 public apply recovery process produced no valid result。事务可已完成，调用方却无法确认。 | 域回归 `evals/tests/test_process_recovery.py` 失败；同一失败 fixture 中直接调用 apply resume 复现 263 字符目标、exit 2、os.replace WinError 3。7 份 family2 support 已统一 native IO，并保留 safe 路径校验。原硬退出测试的目标匹配兼容 native 前缀，以同一文件身份识别；仍在真实 replace 后 os._exit，不缩短测试路径。 | 修复已落；全部 support ruff 通过；原公开硬退出／恢复机制在明确重锁的隔离契约与冻结包上全断言通过，证据见 `artifacts/test-tmp/v3-recovery-long-output-native-isolated-02/process-recovery-evidence.json`；最终统一回归另记。 |
| R5 / P1：共享记录缺固定 inventory 时跳过覆盖检查 | `contracts/records.py:validate_ingest_record` 原来允许 scan=None 且无 inventory，只有不可跨机恢复的 `.build` scan_ref 也可通过；P1 历史读取又假定 inventory 存在。 | `test_shared_record_without_fixed_inventory_cannot_skip_unit_coverage` 已实际 RED（DID NOT RAISE）。正式／跨机调用必须自包含固定清单；显式传入 scan 的本机中间验证仍允许。 | 已加 SCAN_INPUT_UNAVAILABLE guard，GREEN。 |
| R6 / P1：空库吞掉已存在来源锁的 Schema 错误 | `contracts/checks.py` 捕获来源锁错误时原来仅在存在卡片时报告，导致 snapshots 为字符串的坏锁也 passed/exit 0；lint 与固定 CI 共用此缺口。 | `test_existing_malformed_source_lock_fails_even_when_library_is_empty` 与编排组 public lint 重放均实际 RED（actual 0 / expected 1）。存在锁必须验证；空库没有锁可明确 N/A。 | 已修；坏锁失败、空库缺锁 N/A 不阻止临时空索引，GREEN。 |
| R7 / P1：历史代码引用错误要求匹配当前 checkout | `contracts/checks.py` 原来对所有 code_gate 卡和全部 sources 要求最新版本一致，使 deprecated 卡无法在旧实现删除后入库，混合卡的 historical 旧 Claim 也拖累 current Claim。§3.2 仅在需关联当前代码时检查最新 checkout，历史依据仍须确切恢复。 | `test_deprecated_code_card_checks_its_exact_original_without_current_checkout`、`test_current_code_check_projects_claim_sources_and_keeps_current_version_strict` 均实际 RED。混合用例使用真实 Git 两版本、完整配置和确切两份来源；当前用途投影通过后，再把 current 引用改成旧字节必须失败。 | 已按非 deprecated 的 current Claim.source_refs/context_ids 投影；所有历史来源仍完整 sha/locator 检查；上述正向和 current 错版本拒绝断言 GREEN。root 同步修 query 的逐 eligible Claim 新鲜度。 |
| R8 / P1：共享 record-only 待复核随本机 events 丢失 | query 原来仅从本机 events 读取阻断；M 只读正式记录的 positive acceptance，忽略明确 pending。来源／配置未变时，新机仍可使用已经登记待查的同一 Claim。§5.10:677、688、690 明确包括已有问题、已有待办及共享处理事实，不限于版本变化。 | `hs-knowledge-index-build/tests/test_review_shared_pending.py` 先以同一 shared/current 查询确实命中，实际 P6/P7 写 defer/pending，实际 Git 提交并 fixture 签名，再删除 `.build`、operations、events、evidence。原冻结实现回放最终仍命中，真实 RED；当前两个参数均 GREEN（原件不变、关联 refs 空／实际 refs 均覆盖）。 | records.rebuild_restrictions 只读共用重建，query/M 消费；按明确目标与前驱 DAG，仅同 Claim 的最终 content 验收或独立 skip 摘要可解除。缺父链、坏记录不能当无问题；原件 update/create 的 partial 进度不等于已验 Claim 无效。 |
| R9 / P1：record-only 无写集合导致真实正式卡关联被误拒 | records 校验 FinalView 时原来仅搜 writes；合法 defer 引用已经存在的卡／Claim，也在真实 P7 报 DANGLING_CARD_RECORD。 | 共享 pending 的实际 P7 首轮反例及编排组 P6 正反例均确认。 | FinalView 按实际正式根 + 写 − 删构造关联查找，来源锁同样叠加；不读可信 CI 程序根的知识数据；无关坏卡不阻止登记失败事实，虚构目标仍拒。当前共享 pending 两个端到端参数含真实 refs 均通过。 |
| R10 / P1：手动 lint／CI 没有可由 JSON 使用的历史 refs 校验器 | records 组原来传 view=None、可选 Python callback；CLI JSON 没有 callback，真实卡／Claim 真实性被跳过。首个 Git commit 中完整 inventory + phantom refs 的正式记录竟完整 passed/exit 0。 | `test_fixed_ci_rejects_phantom_formal_record_refs_without_python_callback` 实际 RED 后 GREEN；另确认 path-only phantom 不能靠 unrelated archive 对象套路径通过。 | 固定 resolver 使用完整候选视图、声明 SHA 的历史 Markdown 对象与同知识根只读 Git 历史；严格正文 hash、Card ID、Claim。JSON 历史恢复 0、缺旧正文 2、坏 archive hash 1、精确正文无 Claim 1、实际 Git 两版恢复 0 均 GREEN。正式记录还验最终 P7 状态与前驱；P6 中间态不套最终状态。 |

编排组另以公共 source-scan 确认 unit.progress 合法对象形状 `{"status":...}` 被直接集合成员运算抛 unhashable dict；已交编排组局部 normalize，保持共享契约，不以缩窄 Schema 隐藏问题。

## M-only 处理记录的配套校验

与编排组对接后，记录新增 `maintenance_dispositions`，按 `scan.current_context.affected_claims` 去重后的 Card/Claim 精确覆盖，单元 ID 固定为 `maintenance:<card>#<claim>`。没有 raw 变化不代表可以丢弃代码／配置待复核。`evals/tests/test_governance_v3.py::test_record_cannot_drop_maintenance_claims_when_raw_has_no_changes` 已见 RED 后修复为 GREEN；record-only 不能借此采用 content。

## 通过与尚未证明的范围

- 治理共用公开测试最后定向 30 个通过；独立 lint package 另有 1 个公开失败安全测试，共 31 passed（`artifacts/test-tmp/v3-governance-record-resolver-final-2`）。共享 pending 的两个实际 Git／P6／P7／新机查询场景另测 2 passed。正式库 lint 无需 catalog、只读范围、多类问题汇总、坏报告拒绝、来源定位、可信 CI 与候选程序隔离均有合成公共 seam。
- 新 `validate_current_code_identity` 检查精确配置与受保护 policy、真实 Git root/origin/HEAD、全部已接纳相关文件（含未提交字节）及 dirty 状态、Target/build/profile 与构建产物指纹。完整正向／变更行为由 root 的实际 fixture 集成回归覆盖；摘要不成为语义授权。
- 本次没有把用户暂缓的 search 索引过期检查列成问题；没有要求把所有 Skill 合成引擎；没有用文件名不同认定既有能力缺失。
- 本地测试和固定 runner 契约不证明受保护远端 CI 已部署。真实宿主触发、真人、真实六 Target 和权限隔离仍需各自证据。

最终通过数、锁身份与全量执行结果以本轮 V3 验收记录为准。本文件保留实际 RED 原因，修复后不能删掉反例或降低断言取得通过。
