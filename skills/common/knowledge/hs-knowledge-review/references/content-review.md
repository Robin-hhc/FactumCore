# 审阅与固定检查请求

## P4 请求

调用 `.\knowledge.cmd review --input REQUEST.json --json`。使用本次真实引用：

| 字段 | 填写方式 |
|---|---|
| `operation_id`、`view_ref` | 本轮操作和最终完整候选 |
| `semantic_plan_ref` | 对应 P2 计划；省略时从视图取得 |
| `sampled_unit_ids`、`unreviewed_unit_ids` | 实际已审与未审单元，覆盖适用处置且不重复；有适用项时至少审一项 |
| `reason` | 非空的抽样／审阅范围理由 |
| `findings` | 显式问题列表；无问题也传 `[]` |
| `code_review` | 仅代码／混合稿使用，见[代码依据](code-evidence.md) |
| `inputs` | 本次固定检查确需的原版、代码或历史卡材料；不从声明生成通过凭证 |

每个 finding 用 `unit_id` 指向已审单元，提供真实 `evidence`、非空 `reason` 和 `return_to:"P1"|"P2"|"P3"`。适用集合包括内容、实质 skip、defer、failed、uncovered 和维护单元；由真实 P1 证明已处理且未变的 skip 才可免于本轮抽查。

CLI 自动核计划、扫描、视图及返工绑定。新稿采用新视图；不要手工改旧报告或伪造前序引用。

## 读取完整结果

内容问题阻断时，固定检查注明未执行。审阅无阻断后执行一次完整候选检查；内容批在同次已全验的临时索引上执行原 `target_queries`。

读取 `index.build` 检查项中的 `candidate_queries`：逐例用途、预期／实际卡与 Claim、同候选精读及资格缺口。`TARGET_QUERY_EXPECTATION_FAILED` 回 P2；`TARGET_QUERY_INPUT_UNAVAILABLE` 保持未完成。仅记录批不构建内容索引。

报告状态 `passed`、`failed`、`incomplete` 分别对应退出码 0、1、2。局部检查的通过只覆盖其声明范围；P4 使用完整候选范围。

## 历史卡材料

检查旧记录需要确切旧卡时，使用 P1 已保留的 `inputs.historical_card_objects:{sha256:absolute_file}`。复用实际旧正文和摘要，不用新稿拼造旧版。材料不足保持缺口并回 P1。

## 独立固定检查

默认 `lint` 检查正式完整库。检查候选时传 `{"mode":"candidate","view_ref":"实际视图引用"}`；明确局部检查时加 `scope:{kind:"local",paths:[...]}`。报告写入新位置，不修改卡、来源、规则或已有证据。

普通正式检查和 CI 不依赖私人作者计划或 P4 审阅记录。它们复用固定规则，但不替代独立内容判断。

## 独立审阅记录

`.\knowledge.cmd lint --action record-review` 使用上面的实际审阅范围、理由、`findings` 与 `semantic_plan_ref`，可加 `view_ref`。它只保存 `content_review_ref`、`review_status` 和抽样事实，不能表示完整 P4 已通过。
