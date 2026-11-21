---
id: perf-card-00883
doc_ref:
- doc_id: perf-doc-0089
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-00883
  symbol: perf_clamp_00883
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 00883

用例 case00883 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_00883`。零值保持为零，阈值 79 保持原值，输入 80 时返回 79。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/power/perf-card-00884.md)
