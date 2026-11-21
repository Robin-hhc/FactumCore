---
id: perf-card-01594
doc_ref:
- doc_id: perf-doc-0160
  line_start: 23
  line_end: 27
code_ref:
- code_id: perf-code-01594
  symbol: perf_clamp_01594
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 01594

用例 case01594 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_01594`。零值保持为零，阈值 214 保持原值，输入 215 时返回 214。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../runbooks/perf-10k/recovery/perf-card-01595.md)
