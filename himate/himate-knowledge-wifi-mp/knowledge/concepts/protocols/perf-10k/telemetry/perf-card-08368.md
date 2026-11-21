---
id: perf-card-08368
doc_ref:
- doc_id: perf-doc-0837
  line_start: 47
  line_end: 51
code_ref:
- code_id: perf-code-08368
  symbol: perf_clamp_08368
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 08368

用例 case08368 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_08368`。零值保持为零，阈值 85 保持原值，输入 86 时返回 85。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/telemetry/perf-card-08369.md)
