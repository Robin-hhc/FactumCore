---
id: perf-card-05600
doc_ref:
- doc_id: perf-doc-0560
  line_start: 59
  line_end: 63
code_ref:
- code_id: perf-code-05600
  symbol: perf_clamp_05600
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 05600

用例 case05600 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_05600`。零值保持为零，阈值 90 保持原值，输入 91 时返回 90。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/recovery/perf-card-05591.md)
