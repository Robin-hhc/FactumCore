---
id: perf-card-08386
doc_ref:
- doc_id: perf-doc-0839
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-08386
  symbol: perf_clamp_08386
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, power]
lifecycle: stable
---
# 省电轮询阈值用例 08386

用例 case08386 记录 省电轮询中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 power。

## 行为与验证

实现函数为 `perf_clamp_08386`。零值保持为零，阈值 142 保持原值，输入 143 时返回 142。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/power/perf-card-08387.md)
