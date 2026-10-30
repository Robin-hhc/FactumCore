# 候选稿请求

## 成稿请求

默认动作 `run`，正常请求使用：

| 字段 | 内容 |
|---|---|
| `operation_id` | 本次操作 |
| `semantic_plan_ref` | 已保存的作者内容计划 |
| `material_ref` | 可省略，默认取计划绑定的材料；显式值仍须匹配 |
| `cards` 或 `decisions` | 本次实际完整卡稿和卡动作，见下文 |
| `context_ref` | 需要时使用本次实际代码／配置上下文；不能替换材料已采用的上下文 |

材料已经绑定 `bundle_ref` 时从实际材料解析，勿重新捕获。P2 的原查询随计划保留，不在 P3 改写。

代码门禁稿采用 P1 材料绑定的完整 `project_context`，无需手写文件清单或工具身份。缺少所需源码时先回 P1 定向备料；显式旧上下文不完整时保留真实缺口，不在 P3 修改绑定或补造通过记录。

### 简单卡稿与显式动作

`create/update/defer` 可用 `cards: {CardID: draft_ref}`，或卡稿输入列表；稿件引用指向 知识根内 `.build/` 的完整 Markdown 文件。

合并、拆分、退役须显式提供 `decisions`。每项使用 `candidate_id/decision/reason/card_inputs`，按动作补充 `replaces`、`claim_mapping`、`retired_claim_ids`、`related_card_inputs`；暂缓说明 `owner/next_step`。`card_inputs` 可为稿件引用字符串，或含 `path`、可选 `target_path` 的对象。

六种动作保持 `create/update/merge/split/deprecate/defer`。现有卡保留身份与路径；新卡不覆盖其他卡或控制文件。合并、拆分及旧 Claim 去向来自作者明确决定，不由装配脚本猜测。P4 再审实际稿件是否忠实执行这些决定。

### 来源与代码引用

按卡片规范保存 `evidence_ref/source_id/snapshot_id/locator` 和 `Claim.source_refs`。活动卡中的代码来源需要实际支持符号及必要消歧的 `code_ref`，不能用 file／range兜底；同文件多符号使用不同 `evidence_ref`。历史恢复和 deprecated 卡保留原兼容契约。

原件位置通过正式来源字段和路径文字展示。本地 Markdown 链接须指向候选视图中的受管文件，不能用指向 raw 的相对链接代替来源绑定。

CodeGraph 仅辅助定位，实际代码和适用条件仍来自本次材料；不保存内部图节点 ID、不推断宏或构建。纯文档无需虚构代码来源。P3 保存完整声明与字节，符号解析、证据支持和质量复核交 P4。

无实际 Target 的静态源码结论使用 guidance／historical、unknown，`scope.contexts` 和 Claim 的 `context_ids` 均为空数组。`verification_requirements` 只填 `semantic-support/build-support/runtime-support` 中实际所需项，条件说明另写文字字段。

## 结果与交接

成功阶段 `ready` 返回 `plan_ref/plan_digest`、`view_ref/view_digest`、`disposition_preview_ref`、`summary_ref`、`batch_kind` 和 `review_mode`。跟随实际结果引用读取，不手工拼接输出文件名。

候选保存完整 `input_snapshot` 与将发布的字节、最终引用映射；P6 发布同一内容，不在发布时修补卡稿。处置预览保留计划的单元、动作及卡／Claim引用，供 P5 机械转写。

`record_only` 批只保存空写集和已定处置预览，不产生内容稿件或内容检查通过声明。所有新稿和请求／输出留在本操作暂存，正式卡、导航、来源锁与证据在 P6 前保持原状。

## 修订

```powershell
.\knowledge.cmd view-materialize --action revise --input REQUEST.json --json
```

使用新 `operation_id`、实际 `previous_view_ref`、非空 `revision_reason`，其余作者输入与正常成稿一致。

- 仅 P3 改稿：明确采用前序视图绑定且未变化的计划与材料。
- 返回 P1/P2：先采用它们产出的新材料／计划，再保存新稿。

原扫描与处理单元身份保持，旧工件不覆盖；新视图重新交 P4。原计划已冻结但尚无 view 时，不能靠改材料、重写计划或伪造前序 view 接续，保留实际停点。

## 只读描述

`--action describe` 接收实际操作和 `view_ref`，只报告该已保存候选的引用、来源、基线与限制。缺失或绑定不符就返回真实错误，不重新成稿或替代质量审阅。
