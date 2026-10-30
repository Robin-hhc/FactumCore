# 独立检索回归

正常 `batch` 已执行 P2 原冻结查询，本页仅用于明确要求的独立 generation 回归或报告复验。

## 请求

```text
python K/knowledge.py apply --action regression --input REQUEST.json --json
```

```json
{"operation_id":"独立回归ID","generation_ref":"实际代次manifest引用","expected_active":null,"cases":[{"id":"目标可检索","query":"实际检索词","purpose":"guidance","context":{},"required":["实际卡ID"]}]}
```

`expected_active` 使用该次 `index-build` 返回的原活动指针摘要；首次代次才是 null。每例包含唯一 `id`、非空 `query`、真实 `purpose/context` 及明确预期：非空 `required`、非空 `forbidden` 或 `expected_order`（可显式为空）。可选 `top_k` 默认 5，`expected_claim_ids`／`forbidden_claim_ids` 使用 `card#claim`。

独立请求可传实际 `view_ref/apply_result_ref` 采用其中用例；显式 cases 用于独立任务。正常 batch 的用例始终来自原冻结视图，不接受用请求替换。

## 结果与复验

动作校验真实代次，执行断言并同代读取；截断或预期不符不能通过。失败返回 `passed:false`、`activated:false` 及实际问题；全部通过后才按原基线尝试 CAS 激活。

不能通过换用途、放宽断言或替换基线修复失败。回归仅证明本组实际检索行为，不能代替语义复核。

`--action regression-verify` 用确切 `report_ref` 重跑该报告原代次和原用例，不激活。不要替换 generation、cases 或 expected_active；成功复验与实际激活是不同事实。
