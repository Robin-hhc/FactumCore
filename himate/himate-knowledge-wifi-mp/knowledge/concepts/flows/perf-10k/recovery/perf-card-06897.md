---
id: perf-card-06897
doc_ref:
- doc_id: perf-doc-0690
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-06897
  symbol: perf_clamp_06897
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 06897

用例 case06897 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_06897`。零值保持为零，阈值 227 保持原值，输入 228 时返回 227。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/recovery/perf-card-06898.md)
