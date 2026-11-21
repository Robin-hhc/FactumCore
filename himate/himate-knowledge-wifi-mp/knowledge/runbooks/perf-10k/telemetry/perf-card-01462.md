---
id: perf-card-01462
doc_ref:
- doc_id: perf-doc-0147
  line_start: 11
  line_end: 15
code_ref:
- code_id: perf-code-01462
  symbol: perf_clamp_01462
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 01462

用例 case01462 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_01462`。零值保持为零，阈值 211 保持原值，输入 212 时返回 211。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../glossaries/perf-10k/telemetry/perf-card-01463.md)
