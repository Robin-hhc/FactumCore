---
id: perf-card-05385
doc_ref:
- doc_id: perf-doc-0539
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-05385
  symbol: perf_clamp_05385
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 05385

用例 case05385 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_05385`。零值保持为零，阈值 170 保持原值，输入 171 时返回 170。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/power/perf-card-05386.md)
