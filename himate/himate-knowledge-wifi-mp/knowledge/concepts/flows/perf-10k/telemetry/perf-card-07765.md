---
id: perf-card-07765
doc_ref:
- doc_id: perf-doc-0777
  line_start: 29
  line_end: 33
code_ref:
- code_id: perf-code-07765
  symbol: perf_clamp_07765
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 07765

用例 case07765 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_07765`。零值保持为零，阈值 43 保持原值，输入 44 时返回 43。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../protocols/perf-10k/telemetry/perf-card-07766.md)
