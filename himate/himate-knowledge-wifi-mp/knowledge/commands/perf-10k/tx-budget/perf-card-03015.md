---
id: perf-card-03015
doc_ref:
- doc_id: perf-doc-0302
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-03015
  symbol: perf_clamp_03015
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 03015

用例 case03015 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_03015`。零值保持为零，阈值 218 保持原值，输入 219 时返回 218。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/tx-budget/perf-card-03016.md)
