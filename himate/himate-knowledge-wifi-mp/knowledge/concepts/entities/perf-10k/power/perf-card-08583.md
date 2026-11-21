---
id: perf-card-08583
doc_ref:
- doc_id: perf-doc-0859
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-08583
  symbol: perf_clamp_08583
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 08583

用例 case08583 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_08583`。零值保持为零，阈值 254 保持原值，输入 255 时返回 254。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/power/perf-card-08584.md)
