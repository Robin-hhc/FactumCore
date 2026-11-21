---
id: perf-card-05586
doc_ref:
- doc_id: perf-doc-0559
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-05586
  symbol: perf_clamp_05586
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 05586

用例 case05586 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_05586`。零值保持为零，阈值 101 保持原值，输入 102 时返回 101。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/power/perf-card-05587.md)
