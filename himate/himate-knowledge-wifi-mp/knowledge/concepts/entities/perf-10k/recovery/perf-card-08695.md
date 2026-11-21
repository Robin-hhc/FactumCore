---
id: perf-card-08695
doc_ref:
- doc_id: perf-doc-0870
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-08695
  symbol: perf_clamp_08695
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 08695

用例 case08695 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_08695`。零值保持为零，阈值 166 保持原值，输入 167 时返回 166。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/recovery/perf-card-08696.md)
