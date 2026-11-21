---
id: perf-card-09166
doc_ref:
- doc_id: perf-doc-0917
  line_start: 35
  line_end: 39
code_ref:
- code_id: perf-code-09166
  symbol: perf_clamp_09166
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 09166

用例 case09166 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_09166`。零值保持为零，阈值 205 保持原值，输入 206 时返回 205。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/telemetry/perf-card-09167.md)
