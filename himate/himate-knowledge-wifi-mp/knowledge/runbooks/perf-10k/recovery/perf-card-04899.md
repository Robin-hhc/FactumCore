---
id: perf-card-04899
doc_ref:
- doc_id: perf-doc-0490
  line_start: 53
  line_end: 57
code_ref:
- code_id: perf-code-04899
  symbol: perf_clamp_04899
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 04899

用例 case04899 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_04899`。零值保持为零，阈值 125 保持原值，输入 126 时返回 125。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/recovery/perf-card-04900.md)
