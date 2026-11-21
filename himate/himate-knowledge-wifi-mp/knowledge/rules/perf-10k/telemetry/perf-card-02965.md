---
id: perf-card-02965
doc_ref:
- doc_id: perf-doc-0297
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-02965
  symbol: perf_clamp_02965
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 02965

用例 case02965 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_02965`。零值保持为零，阈值 115 保持原值，输入 116 时返回 115。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../commands/perf-10k/telemetry/perf-card-02966.md)
