# 内容计划请求

## 计划字段

默认动作 `plan`。使用当前操作、实际知识根和本次材料；可显式传 `--output` 保存响应。

| 字段 | 内容 |
|---|---|
| `material_ref` | 本次阅读材料引用，必填 |
| `scan_ref` | 材料绑定的真实扫描，正常 Workflow 使用；独立材料目标不伪造全库扫描 |
| `author_id` | 负责本批判断的作者标识，必填，不作身份认证 |
| `units` | 有扫描时逐项覆盖 `scan.units`，无扫描时覆盖 `material.units`：`unit_id/outcome/reason`；补充代码目标作为证据，不另造扫描单元 |
| `maintenance_units` | 实际受影响卡／Claim的独立处置，`unit_id` 为 `maintenance:<card>#<claim>` |
| `claim_changes` | 逐 Claim 的明确比较，字段见下文 |
| `card_actions` | 每个目标卡的明确动作，字段见下文 |
| `target_queries` | 内容批必填的代表查询与预期；纯处置批没有内容查询 |

来源与维护单元的 `outcome` 为 `content/skip/defer/failed/uncovered`。完整覆盖本次实际观察，不凭已有卡引用就声称整份来源完成。

### Claim 与卡片动作

`claim_changes` 每项包含 `unit_ids`、`card_id`、`claim_id`、`action`、`before`、`after`、`conditions`、`evidence`、`preserved`、`reason`；动作是 `create/update/preserve/retire`。同一 Claim 的多源判断合成一项，不丢失保留部分或旧依据。

`card_id/claim_id/action/conditions/reason` 均为非空字符串；`conditions` 用文字说明条件，不传数组或对象。`unit_ids` 是非空的实际单元 ID 数组，`evidence` 提供非空真实依据。`before/after/preserved` 三个键必填；新建时可用 `null` 或 `[]` 明示没有旧结论或保留项，不编造前态。

`card_actions` 每项包含 `card_id/decision/author_id/unit_ids/reason`。六类决定为 `create/update/merge/split/deprecate/defer`。同主题重复才合并，独立主题混装才拆分；普通更新保留稳定身份，旧 Claim 明确保留、改变或退役。

每个单元还固定 `record_action/card_refs/claim_refs`，供 P5 直接转写。只有一种实际卡动作时脚本可归一化；同单元涉及多种卡动作时，作者须明确指定实际动作之一作为 `record_action`，不能留给 P5 猜。

## 查询用途与预期

每例使用唯一 `id`、实际 `query` 和可检查预期：`required`、`forbidden` 或 `expected_order` 至少一种。卡身份用实际 CardID；需要锁定目标结论时使用 `expected_claim_ids`／`forbidden_claim_ids` 中的 `CardID#ClaimID`。

| `purpose` | 要验证的结论 |
|---|---|
| `current` | 当前用途，Claim的 `usage`、范围／上下文与当前证据须匹配 |
| `implementation` | 满足当前用途，且依据为 `implementation` 或 `measurement` |
| `guidance` | 声明条件内的背景或指导；未知适用性不等于当前产品行为 |
| `historical` | 指定历史结论与可恢复原版依据，不声称当前适用 |

省略 `purpose` 默认 `current`，因此应主动按目标 Claim 选择。代码链接仅提供定位，不能把设计依据提升为实现依据。

新增／修改结论的正向用例宜声明目标 Claim，避免同卡其他结论偶然满足查询；负向用例可只声明排除或明确空结果。退役卡验证当前排除或历史行为。P4 在最终候选上执行原查询及同代精读；预期不满足回作者重判，不自动换用途或修改预期凑通过。

## 结果与返工

成功返回 `semantic_plan_ref/semantic_plan_digest`、原查询和 `content_planned`。这是本次作者数据，完整卡稿由 P3 生产。

### 返工

已有候选的重判使用新 `operation_id`、真实 `previous_view_ref` 和非空 `revision_reason`。材料未变可明确采用前序视图绑定的材料；已补料则采用新版本。沿用仍有效的原扫描及单元身份，不伪造新观察，也不覆盖旧计划。

计划已保存而尚无前序 view 时，不能重写同操作计划或编造 view 解决补料问题，应保留不可变绑定的实际停点。来源范围或字节已变时回来源阶段刷新相应输入。

请求、响应和新计划只写本操作暂存，正式事实由后续发布建立。旧字节生产或审阅请求不在本入口继续执行，分别使用 P3 或 P4 对应能力。
