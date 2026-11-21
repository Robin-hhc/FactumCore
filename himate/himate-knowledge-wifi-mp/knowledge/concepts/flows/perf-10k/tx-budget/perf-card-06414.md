---
id: perf-card-06414
doc_ref:
- doc_id: perf-doc-0642
  line_start: 23
  line_end: 27
code_ref:
- code_id: perf-code-06414
  symbol: perf_clamp_06414
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 06414

用例 case06414 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_06414`。零值保持为零，阈值 233 保持原值，输入 234 时返回 233。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/tx-budget/perf-card-06415.md)
