# P3/P4/P6/P7 实现及验证记录

设计基线保持：`docs-llm-wiki/sdd/knowledge-v3/baseline/知识库详细设计.md`，SHA-256 `32df6c9505f3f7c6e8220f90a02a030641d5c9f39d0402ac80154b6556ad2f54`。审计见同目录 `v3-audit-content-apply.md`。此文件记录本子任务实际工作，不修改设计正文或 v1/v2 历史。

## 实现

- `change-plan --action plan` 在稿前固定逐 Claim 比较、旧结论保留、条件、依据、单卡作者、欠账和本批查询；`review` 固定独立上下文声明、风险样本与未抽项、明确问题及返回节点。六种卡动作不增加 skip；raw 与维护单元分开，维护单元精确绑定 `scan.current_context.affected_claims`，不伪造 raw。
- 最终卡稿必须对应计划；同 Card/Claim 只一条裁决，改变不能来自 skip/defer/failed 单元；目标查询覆盖实际计划目标，不能只查询无关旧卡。更新旧卡必须逐条裁决；preserve 的正文、scope、定位、来源和验证字段不可暗改或删除。
- 同一 snapshot 的内容身份仍不可变，仅允许实际核验成功的 Git 恢复描述升级；已有 Git 原版保留，不因 HEAD 的无关提交重写历史来源版本。
- 混合视图保留完整字节身份及卡级适用分区。真实人动作仍验证受信公钥、完整视图、挑战、真人 actor、决定和期限；代码仍验证受信语义签名、真实上下文及逐 Claim 正面证据。混合视图两类证明缺一不可，不把文档卡强行送代码核验。
- P4 展示前与 candidate-inspect 复用确定性预检；P7 除校验完整 native lint 报告外，再对当时实际全库合成视图执行固定检查。旧报告的公开 digest 不能替代实际检查。最终内容复核的作者冲突、未解问题及身份失配均阻断。
- P6 共享记录作为原 CAS/journal 的额外受控 entry，同批写入 `logs/ingest/<id>.yaml`；不修改人已确认的卡／导航／来源锁字节。P7 补记真实落位并复验，从真实卡及已验证 proof 派生可共享 acceptance 摘要。仅记录批次禁止知识写入，失败/defer 的单元进度不提升成已完成。
- P7 正常批先公开鉴真实际 apply，再完整验证索引、执行 P3 固定目标查询及同代正文/Claim 检查。提交就绪节点公开重验这些门禁，不能接受伪造 passed query JSON、空 case 或调包后的旧卡问题。运行故障只重试收尾，原 apply 结果与恢复引擎保留。
- `publish-handoff` 返回精确 `commit_files`；授权宿主提交后，`verify-submission` 读取实际 HEAD Git 对象，核对逐文件字节、删除项和本批范围，才报告 submitted。节点不执行 Git 写入或 push/merge，ready 不等于已有提交。
- 旧 governance-handoff 改为同一 ingest 的 P4 停点，不再指向已删除的 lint Workflow；配套 Skill、请求说明和复核指南已同步。

## 已执行的验证

均使用 `E:\FactumCore\.scratch\domain-root-rename-20261021\venv\Scripts\python.exe`。新测试只用隔离合成 raw/代码、固定 Git 对象和受限制的 synthetic 签名器，没有读取正式 raw/knowledge 或 gold。

| 验证 | 实际结果与证据 |
|---|---|
| P3 无 draft 可计划、固定覆盖、实质 skip 抽查、同 Claim 冲突、skip 偷写、无关查询、精确 Git 恢复升级、M-only、已完成扫描跳过免重审 | 各新功能先观察到对应 RED，再修复；最终 `test_v3_plan.py` 9 项 + preserve 3 项 + query gate 1 项在 `--import-mode=importlib` 下一并 13 passed，21.15s |
| preserve 删除／静默改正文／静默改用途 | `test_review_preserved_claim.py` 3 passed，9.46s；独立审计的删除反例先 RED |
| 原 CAS、恢复、外部修改、假同意、原始路径注入、独占写锁 | `apply/tests/test_apply.py` 12 passed，1.11s；没有弱化硬退出／CAS／外部修改保护 |
| 混合稿两类受信证明 | `local-check/tests/test_public_code_gate.py -k mixed` 最新 1 passed，6.56s；少真人证明先拒绝，齐备后实际 apply |
| 真人确切展示 | `confirmation-prepare/tests/test_prepare.py` 3 passed，包括混合完整字节展示；原 code-only 免真人路由保留 |
| 仅记录实际 apply → 公开鉴真 → 精确清单 → 真实隔离 Git 提交 → verify-submission | `apply/tests/test_public_governance.py -k record_only` 1 passed；blocked 单元没有变成 completed |
| 内容批无 target-query 证明不得就绪 | 公开原测试先 RED（错误返回 awaiting_external_publish），修复后 GREEN |
| caller 用无关 cases 替换计划 | `query-regression/tests/test_v3_gate.py` RED→GREEN；测试解释器隔离，避免各 Skill support 导入缓存相互污染 |
| 完整当前流程正向与旧 lint 报告反例 | `test_v3_flow.py` 两参数 2 passed，101.25s；已提交 raw 自动 Git 恢复→scan/material→P3→稿→独立复核→fixture 真人动作→native lint→记录→apply→实际索引/query/read→精确 Git 提交→submitted |
| 旧 lint 已过后新增候选写集外断链、伪造 passed review 同作者、未解 findings | 最终 `test_v3_flow.py -k True --import-mode=importlib` 1 passed，52.50s；先拒绝且卡未落位，修正后完成全链。旧 lint 断链先实证 RED（原实现错误 committed） |
| 所属 12 个 Skill 包 ruff | 全部通过（含生产、测试及当时共用 support）；共用 native IO 后续由治理子任务统一验证 |

完整流程测试对本次 Skill 包复制冻结后再生成 catalog，避免并行编辑导致 package digest 漂移。fixture 的治理副本单独重锁，不能代替最终工作区 lock 的全项目回归；最终统一回归由主任务记录。

## 边界

内容复核报告只记录声明的独立上下文，不将公开 digest 视为可信宿主证明。真人与代码语义的签名鉴真链继续独立执行。合成流程通过不证明真实人已确认、真实宿主已安装、六 Target 已接入或权限隔离。

新默认流程强制 v3 字段；原 schema2 请求保留明确兼容入口。正式来源当前支持确切 Git 原版跨机恢复；只有本机临时对象或 dirty 字节而没有受支持的持久恢复条件时，新 P7 阻断，不宣称兼容所有旧本机 evidence 情形。共享摘要成为可信接纳事实仍需主任务实现的真实 Git/publication 信任链；本地 applied 不是 shared admission，也不是 CI/合入。

## 最后来源接口补验

新增的 `SourceResources.recover_snapshot(..., allow_local_fallback=True)` 允许历史读取在 Git 配置／对象不可用时，核对确切保留字节后使用 `local_recovery`。P7 与来源锁升级现在均显式传 `allow_local_fallback=False`：历史可读与正式可跨机恢复分别判断。`local_recovery` 和 `recovery` 同属存储说明；比较同 snapshot 的语义身份时排除这两个字段，SHA/长度/定位/代码身份等其余字段仍须完全相同，且新 Git 原版必须实际恢复成功。

公开 `test_v3_flow.py[historical_fallback]` 先实证 RED：配置移除后公开历史解析仍返回原文，旧 P7 却错误 committed。修后该例及 `[local_only]` 两例 2 passed，30.56s，P7 均 blocked 且卡未落位。同 snapshot 升级增加实际 `local_recovery` 的迁移例 1 passed，3.75s；相关源码／测试 ruff 全部通过。

此处 P7 的通用本机来源拒绝用完整纯文档流程验证；实际 dirty 代码捕获保持本机恢复、实际 committed code 自动登记 Git 原版由编排子任务的公开代码捕获例验证。两种证据范围不能合并声称已完成真实代码卡或六 Target 的端到端验收。

## 补充：实际代码捕获至索引／目标查询正向

新增 `hs-knowledge-local-check/tests/test_public_code_gate.py::test_committed_code_capture_reaches_v3_apply_index_and_target_queries`，复用现有隔离代码、Target、受限制签名 fixture，所有节点均调用实际公开 CLI，没有修改生产代码，也没有手改 capture 输出的 recovery 或 SourceSnapshot。

过程实际执行：预置合法旧卡 → 在隔离代码仓真实提交函数返回值由 1 改为 2 → actual capture-code 自动生成 `repo_id/commit/path` Git 恢复且 `checked_file_dirty=False` → P1 真实 M 差异（raw inventory 为空）→ P2 接代码子 operation 的 bundle → P3 维护单元计划 → P4 稿和独立复核、逐 Claim 受信 fixture 代码签名 → P5 带确切 `code_checkout` 的 native 全库 lint → P6 共享记录 → P7 严格实际 Git 恢复及同批入库 → 真实索引构建、计划目标 query、同代正文读取和激活。核对 acceptance 的实际 config 指纹和维护处置，结果 **1 passed，42.88s**；测试文件 ruff 通过。

该正向已超出上一节的组件组合范围，证明新的代码入库接点在隔离合成环境可连通；代码仓／Target／构建证据／签名身份仍是明确 synthetic 层次，不证明真实六 Target 业务验收。

装配时明确的接口约束：代码捕获使用独立 source operation，与 raw capture 一样每个不可变 bundle 一份；batch prepare 接 `code_bundle_refs` 后统一绑定批次。若捕获与聚合复用同一个 operation，会因都使用 `capture.json` 而明确报冲突，不能通过覆盖不可变 artifact 消除。编排子任务已负责同步调用指引。官方 capture context 使用 `context_loaded` 和确切 workspace/config 绑定；同一 Claim 的多个 M 原因合并为一个维护单元。
