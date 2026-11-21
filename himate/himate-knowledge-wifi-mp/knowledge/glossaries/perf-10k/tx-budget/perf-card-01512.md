---
id: perf-card-01512
doc_ref:
- doc_id: perf-doc-0152
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-01512
  symbol: perf_clamp_01512
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, tx-budget]
lifecycle: stable
---
# 发送预算阈值用例 01512

用例 case01512 记录 发送预算中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 tx-budget。

## 行为与验证

实现函数为 `perf_clamp_01512`。零值保持为零，阈值 65 保持原值，输入 66 时返回 65。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/tx-budget/perf-card-01513.md)
