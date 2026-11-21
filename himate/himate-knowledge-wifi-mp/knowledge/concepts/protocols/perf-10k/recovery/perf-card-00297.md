---
id: perf-card-00297
doc_ref:
- doc_id: perf-doc-0030
  line_start: 41
  line_end: 45
code_ref:
- code_id: perf-code-00297
  symbol: perf_clamp_00297
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 00297

用例 case00297 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_00297`。零值保持为零，阈值 77 保持原值，输入 78 时返回 77。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/recovery/perf-card-00298.md)
