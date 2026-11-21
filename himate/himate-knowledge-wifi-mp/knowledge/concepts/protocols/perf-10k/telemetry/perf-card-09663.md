---
id: perf-card-09663
doc_ref:
- doc_id: perf-doc-0967
  line_start: 17
  line_end: 21
code_ref:
- code_id: perf-code-09663
  symbol: perf_clamp_09663
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, telemetry]
lifecycle: stable
---
# 遥测采样阈值用例 09663

用例 case09663 记录 遥测采样中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 telemetry。

## 行为与验证

实现函数为 `perf_clamp_09663`。零值保持为零，阈值 188 保持原值，输入 189 时返回 188。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../../rules/perf-10k/telemetry/perf-card-09664.md)
