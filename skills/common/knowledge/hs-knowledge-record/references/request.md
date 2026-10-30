# 记录请求

## 正常 P5

```json
{"operation_id":"CURRENT_OPERATION","view_ref":"ACTUAL_VIEW_REF"}
```

用本次真实值替换示例。CLI 由 `view_ref` 解析语义计划、固定扫描和处置预览，核对后机械转写；一般不需要额外传递这些已经绑定的字段。

| 可选项 | 使用时机 |
|---|---|
| `record_id` | 明确指定记录身份；省略时用操作 ID |
| `semantic_plan_ref`、`disposition_preview_ref`、`scan_ref`、`material_ref` | 当前调用明确给出时，必须与视图实际采用项一致 |
| `lint_ref`、`skip_sample` | 保存真实检查或抽样事实；不是调用前置通过凭证 |
| `pending` | 明确保留的欠账，不补写未执行的成功 |

`recorded` 返回 `record_ref`、`ingest_record_ref`、`record_digest`、`record_path`、`batch_kind`。前两个引用指向暂存中的待发布记录；`record_path` 是正式目标路径，只有 P6 实际发布后才成为正式处理事实。

## 返工与记录边界

返工使用新视图所属操作，保留原扫描身份和精确前序绑定。当前视图决定了记录动作、卡／Claim引用、理由和维护处置；不要传另一套 `dispositions` 覆盖它们。若需改变结论或稿件，暂停当前记录，交明确修订任务或由宿主重排；P5 不自行跳转上游阶段。

多卡动作需要作者在 P2 明确 `record_action`，P5 不猜其中一个。材料不足或作者选择 `defer/failed/uncovered` 是应保留的欠账；记录存在不等于该范围完成。纯代码维护可以没有 raw 单元，维护单元保持独立身份。

## 独立记录

只有任务明确要求独立登记时，才使用实际 `scan_ref` 和完整的显式 `dispositions`，没有真实视图就不声称经过候选审阅。每个处置要覆盖真实单元并保留动作、理由、实际指纹及进度；不能借独立模式改写已有视图绑定的决定。

需要改变结论、卡稿或来源登记时走明确修订并重新审阅；本入口不隐式重做上游阶段，也不提交 Git、CI 或合入。
