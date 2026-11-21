---
id: perf-card-01324
doc_ref:
- doc_id: perf-doc-0133
  line_start: 23
  line_end: 27
code_ref:
- code_id: perf-code-01324
  symbol: perf_clamp_01324
  line_start: 3
  line_end: 7
tags: [perf-10k, radio, retry]
lifecycle: stable
---
# 重试计数阈值用例 01324

用例 case01324 记录 重试计数中无线队列计数的边界行为。

## 适用条件

合成请求进入归一化阶段。参数为无符号计数，所属测试组为 retry。

## 行为与验证

实现函数为 `perf_clamp_01324`。零值保持为零，阈值 106 保持原值，输入 107 时返回 106。
本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，定位到代码定义可确认上界和返回值。

[同原件下一用例](../../../flows/perf-10k/retry/perf-card-01325.md)
