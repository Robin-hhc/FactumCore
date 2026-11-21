---
id: perf-card-06285
doc_ref:
- doc_id: perf-doc-0629
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-06285
  symbol: perf_clamp_06285
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 06285

用例 case06285 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_06285`。零值保持为零，阈值 32 保持原值，输入 33 时返回 32。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/power/perf-card-06286.md)
