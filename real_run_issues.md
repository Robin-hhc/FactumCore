# FactumCore 知识库系统：待解决问题清单（2026-10-28）

## 出现了p3时agent已确定4卡计划后，先创建单卡确定流程的问题，需求确认是否是skill内提示词导致，还是agent偶现的自发行为，执行记录如下：
P2 捕获信息完整：source_id = raw:f3f6a07b2381a32624d0d4f89c3f3858，snapshot_id = raw:4504fb3b09244a1b884e1fc2967356f410ab5db6560b66c1e9d80f2fd524184a，locator 为 locator_map。卡中 sources 将引用这个 source_id/snapshot_id，locator 用原文行段。

现在设计语义计划。基于已读原文，将 HWDL 收发设计说明书拆为 4 张卡（每卡含多个 Claim）：

hwdl-tx-flow（flow）：HWDL TX 数据帧收发链路（5.1，11 个节点）
hwdl-rx-flow（flow）：HWDL RX 数据帧收发链路（5.2，4 个节点）
hwdl-frame-protocol（protocol）：HWDL 帧体格式与 SNAP/PID 变换（3/4 章）
hwdl-tx-command（command）：hwdl_tx 测试命令（5.3）
全部为 create 动作，Claim 均为 create。所有 Claim 的 evidence_kind: design、usage: guidance（设计文档，未实现验证），scope 适用 mp1x(1108)/mp17c(1107c) 两代旗舰、host+device 两侧。

先构造计划请求。注意：

units：1 个单元（raw-f3f6a07b2381a32624d0d4f8），outcome=content
claim_changes：每张卡的每个 Claim 一条
card_actions：每张卡一条，decision=create
target_queries：覆盖 4 张卡，purpose 依据内容（设计文档 → guidance）
编写 P3 请求 JSON 并执行。

先只包含 TX flow 卡验证 P3 校验逻辑是否通过，再扩展其他卡。执行 plan。

P3 plan 成功（phase=content_planned）。但当前计划只覆盖 TX flow 卡，未覆盖 RX flow、帧体 protocol、命令卡。为保证本批原件内容完整覆盖（4 张卡），需要扩展计划。由于语义计划已保存，重新提交完整计划（覆盖所有卡）。

重新构造完整 plan 请求，包含 4 张卡的全部 Claim 与 target_queries。

遇到 OPERATION_CONFLICT：semantic-plan.json 已存在且不可变。同 operation 内语义计划只能保存一次。既然之前的 TX-only 计划已保存，且 P3 要求计划完整覆盖本批内容——但原计划只覆盖了 TX 卡。

正确做法：语义计划属于"作者判断已固定"的产物，若需扩展内容，应创建新 operation（按 SKILL 契约：P5 退回或补料时用新 operation_id）。但当前仍处 P3，同一批原件内容未变，只是我最初的计划不完整。

关键判断：P3 契约允许一个语义计划覆盖本批单元。原 TX-only 计划其实已经合法保存（phase=content_planned）。问题是我希望在同一 op 内重写。由于不可变约束，不能覆盖。

选择：

接受 TX-only 计划，但这样本批原件内容未完全覆盖（RX/protocol/command 未纳入）——不完整。
新建 operation，重新扫描+备料+完整计划——成本高但符合契约。
删除旧 semantic-plan.json，用完整计划重跑——但不可变工件被修改有风险，且 P3 明确"旧工件不覆盖"。
正确路径应是新 operation。但注意：同一原件内容未变，scan 结果仍有效。按契约"原 scan 及单元身份不变"，新 op 可复用原 scan_ref/material_ref 吗？

查看 author_plan 逻辑：material["operation_id"] != ctx.operation 时需要 previous_view_ref（修订上下文）。这是为 P5 退回/补料设计的。当前没有 previous_view，属于首次计划不完整的情况。

重新审视：P3 语义计划本质是作者对内容的一次性判断。我已保存了一份 TX-only 计划。它是否满足"本批单元处置"要求？看校验：units 覆盖了唯一单元，claim_changes/card_actions 覆盖了 content 单元（通过 covered 检查），target_queries 覆盖了计划卡。所以 TX-only 计划通过了所有校验，是合法的语义计划。

但业务上，原件内容包含 RX/protocol/command 三块，只入 TX 卡会导致内容未完整入库。这属于作者判断范围。P3 节点提示说"逐单元确定 content/skip/defer/failed/uncovered 及理由，判断卡和旧 Claim 的新建/更新..."——即作者决定本批建哪些卡。

这里的关键取舍：是"本批只建 TX 卡，其余后续再入"（缩小范围），还是"本批完整建 4 卡"？

由于原文是完整说明书，拆 4 卡是更合理的完整覆盖。但不可变工件已锁死 TX-only 计划。

正确且符合契约的做法：新建 operation 重新走 P1→P2→P3 完整计划。但这样重复 scan/prepare。或者：既然 scan/prepare 都是可复用的（原件未变），新 op 可以复用？不行——material 绑定要求 material 的 operation_id == 当前 op，除非走 previous_view 修订链路。

重新读契约："Returning from P5 after a candidate exists uses a new operation with previous_view_ref and a nonempty revision_reason"。这是 P5 退回场景。当前在 P3，没有 candidate。

实际上最干净的做法：在同一个 op 内无法重写，那就接受当前 TX-only 计划作为本批范围，还是应该用新 op？

让我重新想。P3 的核心输出是 semantic_plan，保存后不可变。作者判断一旦固定（content_planned），本批范围就定了。如果作者认为 TX-only 不够，需要扩大范围——这本质是"作者判断"的修订，但契约里"作者判断已固定"就是出口条件。

我认为正确决策是：本批语义计划应完整覆盖原文内容。由于已在同 op 保存 TX-only 计划，且不可覆盖，最符合契约的推进是新建 operation，复用原 scan 结果（原件未变，scan 指纹一致）作为显式引用？但 author_plan 对跨 op 的 material/scan 需要 previous_view。

实际上，让我重新检查：是否可以删除旧 semantic-plan.json？看 support.py 中 OPERATION_CONFLICT 逻辑，确认不可变语义。

实际上更简单的正确路径：新建 operation 重跑 P1→P3。虽然重复，但这是契约允许且干净的。不过成本是重新 scan+prepare。

等等——重新读节点执行提示："P5退回或P2补料后，用新operation_id、previous_view_ref及revision_reason保存新计划；原scan及单元身份不变"。这暗示新计划可以用新 op + 原 scan。

但 author_plan 校验：material["operation_id"] != ctx.operation 时必须 previous（即 previous_view_ref）。没有 previous_view 就不行。

所以跨 op 复用 material 必须有 previous_view。当前无 previous_view。

结论：不能在同一 op 内重写，也不能无 previous_view 跨 op 复用。那么要么：

接受 TX-only 计划（缩小本批范围），推进到 P4；或
新建 op 完整重跑 P1→P3（全新，不引用旧 op）。
考虑到业务完整性和"内容完整覆盖"原则，以及 P3 出口要求"本批单元、卡和旧Claim处置...已保存"（TX-only 计划已满足该单元的处置），我判断：

本批范围决策：原文内容较多，一次建 4 卡是完整覆盖。但既然计划已冻结为 TX 卡，更合理的做法是在本次 P3 内就完整规划。为此需要新建 op。

不过，重新审视——其实我最初就不该先跑 TX-only。现在补救：由于 semantic-plan.json 不可变，且我不想重复整个 P1/P2，让我检查 support 的 OPERATION_CONFLICT 是否针对"同路径不可变"——也许删除该文件并用完整计划重跑是允许的（因为本批 stage 文件，P7 才清理）。

但契约明确"旧工件不覆盖"。删除是不可取的。

让我换个思路：新 operation 完整重跑是最干净合规的。原件未变，scan 会再次识别为 new（因为无正式记录），prepare 会重新捕获，plan 完整。虽然重复 P1/P2，但确保正确性。

实际上，让我重新确认：是否真的需要完整覆盖 4 卡？P3 节点说"逐单元确定...判断卡和旧Claim的新建..."——作者有裁量权决定本批建哪些卡。TX-only 计划是合法且已保存的。但"三分之二说明书"暗示原文是分批发行的，本批可能只需覆盖已到手的部分内容。

不过原文包含完整的 TX 和 RX 和帧格式和命令——都是"三分之二说明书"的一部分。作者应完整覆盖。

我决定：新建 operation 完整重跑，覆盖 4 卡。这样最干净。

但等等，让我再想想有没有更轻量的路径。查看是否可以在新 op 中通过 previous_view 机制——但当前没有 candidate/view，previous_view 不存在。

所以新 op 必须从 scan 开始。我接受这个成本。

不过，实际上还有一个更务实的考虑：TX-only 计划已经合法保存并可通过。与其重跑整个流程，不如审视这是否真的是问题。P3 的语义计划是作者对"本批"内容处理的决策。如果作者判断本批范围 = TX 卡（flow），那 RX/protocol/command 可作为后续批次（同一原件后续再 scan 时——但原件不会变，scan 会识别为 unchanged 而非 new）。

这就尴尬了：若本批只入 TX 卡，原件内容其余部分（RX/协议/命令）就"丢失"了——因为原件已捕获，后续 scan 该原件为 unchanged，不会触发新卡创建（除非明确修订目标）。

所以完整覆盖是必须的。必须新建 op 重跑。

好，决定：新建 operation，重跑 scan → prepare → 完整 plan（4 卡）。

先删除旧 op？不，保留旧 op（其产物作为历史）。新建 op2。

开始。遇到 OPERATION_CONFLICT：同一 operation 内语义计划已保存（TX-only），不可变不能覆盖。而 TX-only 计划未完整覆盖原件内容（缺少 RX/协议/命令卡），若本批只入 TX 卡，原件其余内容会因后续 scan 识别为 unchanged 而永久遗漏。

正确做法：新建 operation 完整重跑 P1→P3，用完整 4 卡计划。这是契约允许的干净路径（原件未变，新 op 重新 scan/prepare/plan）。

先创建新 operation 并重跑 scan。

## 会议纪要：
关键结论:
知识卡片由AI自动从文档（主流支持MD、PDF、DOC）生成，卡片仅提取边界、版本、关键函数等核心要点，避免全文重复入库；该机制支持将文档与对应代码入口函数、行号及源文档链接，确保Agent可追溯到具体实现。
初步决定优先保障个人本地开发的良好体验，后续通过半日/日级的CI巡检机制修复增量变更导致的知识卡过期问题，实现“尽力而为”的持续一致性，初期的文档上库可不设置CI拦截，可直接放入仓内，待巡检时统一进行蒸馏入库。
基于LLM Wiki方案构建知识卡片系统，核心价值在于将业务知识与代码实现挂钩，通过卡片索引快速定位关键信息，提升Agent在迭代开发或问题定位时的检索效率与准确性。
知识库采用精确匹配的索引机制（非语义匹配），优先保证召回结果的准确性（宁缺勿滥），通过评分与标签过滤缩小范围，避免返回错误结果影响开发效率。
确认知识库需按群组权限（如WiFi 5X和 0X）分开管理，以隔离不同组的敏感文档与代码权限；文档来源主要为设计文档、Spec等，但不强制全部入库，建议仅上传高质量、高价值的核心知识文档。
遗留任务:
完成当前demo调试，保证本地基础功能的通畅并小范围本地发布试用(责任人：黄瀚成；完成时间：10.31)
调研并实现知识卡片入库流程的提速（当前存在入库慢、流程卡顿问题）(责任人：黄瀚成；完成时间：11.31)
完成知识库与外部平台对接，支持软连接到dbox、wiki等(责任人：黄瀚成；完成时间：11.31)
设计知识库可视化管理UI界面（拖拽上传、进度条等），需要能看到可量化的数据(责任人：黄瀚成；完成时间：11.31)
小范围发布demo后，评估实际用户体验(迭代开发/问题定位等效果、易用性)，持续优化并确保在最终展示前有明显提升(责任人：黄瀚成；完成时间：11.31)
评估并处理图片内容的解析与知识抽取能力验证(责任人：黄瀚成；完成时间：待定)
优化用户交互体验，将入库、巡检等流程自动化，用户不感知，仅上库文档并检索(责任人：黄瀚成；完成时间：待定)
调研从代码自动反向生成文档的可行性与效果（类似内源的深度求索功能），以解决无文档场景下的知识积累(责任人：黄瀚成；完成时间：待定)
