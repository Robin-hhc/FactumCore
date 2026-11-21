---
id: perf-card-01085
doc_ref:
- doc_id: perf-doc-0109
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-01085
  symbol: perf_clamp_01085
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 01085

用例 case01085 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_01085`。零值保持为零，阈值 27 保持原值，输入 28 时返回 27。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/power/perf-card-01086.md)
