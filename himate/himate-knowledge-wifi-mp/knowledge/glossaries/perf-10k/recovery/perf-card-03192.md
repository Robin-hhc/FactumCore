---
id: perf-card-03192
doc_ref:
- doc_id: perf-doc-0320
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-03192
  symbol: perf_clamp_03192
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, recovery]
lifecycle: stable
---
# 故障恢复阈值用例 03192

用例 case03192 记录 故障恢复中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 recovery。

## 行为与验证

实现函数为 `perf_clamp_03192`。零值保持为零，阈值 239 保持原值，输入 240 时返回 239。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../concepts/entities/perf-10k/recovery/perf-card-03193.md)
